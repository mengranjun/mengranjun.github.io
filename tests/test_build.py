"""构建器回归检查：使用临时站点，不改动真实文章和生成页面。"""
import contextlib
import io
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import hashlib
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen
from urllib.parse import parse_qs, urlsplit
from html import unescape
from html.parser import HTMLParser

import build


SOURCE = Path(build.__file__).resolve().parent


class MarkdownTests(unittest.TestCase):
    def test_quote_paragraphs_in_both_languages(self):
        for text in ("> Hello\n>\n> World", "> 第一段\n>\n> 第二段"):
            with self.subTest(text=text):
                result = build.md_to_html(text)
                self.assertEqual(result.count("<p>"), 2)
                self.assertIn("<blockquote>", result)

    def test_nested_quote_and_list(self):
        result = build.md_to_html("> 引用\n>\n> > 内层\n>\n> - 一\n> - 二")
        self.assertEqual(result.count("<blockquote>"), 2)
        self.assertIn("<ul>", result)

    def test_balanced_parentheses_in_links_and_images(self):
        for url in ("https://example.com/a_(b)", "https://example.com/a_(b_(c))"):
            self.assertIn('href="%s"' % url, build.inline("[资料](%s)" % url))
        self.assertIn('src="pic_(1).png"', build.inline("![图片](pic_(1).png)"))

    def test_links_keep_code_emphasis_and_url_symbols(self):
        result = build.inline("[**资料** `x`](https://example.com/*test*)")
        self.assertIn('<strong>资料</strong> <code>x</code>', result)
        self.assertIn('href="https://example.com/*test*"', result)
        self.assertIn('<code>[x](url)</code>', build.inline('`[x](url)`'))

    def test_escaped_parentheses(self):
        self.assertIn('href="https://example.com/(x)"', build.inline(r'[x](https://example.com/\(x\))'))

    def test_table_pipes(self):
        for cell in ('`x|y`', r'x\|y', '``x|y``'):
            with self.subTest(cell=cell):
                self.assertEqual(len(build._split_row('| %s | z |' % cell)), 2)
        result = build.md_to_html('| A | B |\n|---|---|\n| `x|y` | z |')
        self.assertEqual(result.count('<td>'), 2)
        self.assertIn('<code>x|y</code>', result)
        self.assertEqual(build.inline('``x|y``'), '<code>x|y</code>')
        self.assertEqual(build.inline('``a`b``'), '<code>a`b</code>')

    def test_numbered_list_blank_lines(self):
        result = build.md_to_html('1. 第一步\n\n2. 第二步')
        self.assertEqual(result.count('<ol>'), 1)
        self.assertEqual(result.count('<li>'), 2)

    def test_plain_markdown_starting_with_long_rule(self):
        self.assertEqual(build.parse_front_matter('----\n\n正文'), ({}, '----\n\n正文'))


class SiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='muroj-test-')
        self.root = Path(self.temp.name)
        for name in ('index.html', 'archive.html', 'about.html', 'tools.html', '404.html',
                     'favicon.svg', 'favicon.ico', 'apple-touch-icon.png', 'og-image.png', 'build.py'):
            shutil.copy2(SOURCE / name, self.root / name)
        for name in ('css', 'js'):
            shutil.copytree(SOURCE / name, self.root / name)
        (self.root / 'posts').mkdir()
        self.post = self.root / 'posts/hello.md'
        self.write_post()
        self.stack = contextlib.ExitStack()
        self.stack.enter_context(patch.object(build, 'ROOT', self.root))
        self.stack.enter_context(patch.object(build, 'POSTS_DIR', self.root / 'posts'))

    def tearDown(self):
        self.stack.close()
        self.temp.cleanup()

    def write_post(self, extra='', body='## 小节\n\n正文', name='hello.md'):
        path = self.root / 'posts' / name
        path.write_text('---\ntitle: 测试文章\ndate: 2026-11-12\ntags: 随笔\n' + extra + '---\n\n' + body,
                        encoding='utf-8')
        return path

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def render(self):
        return build.make_build_plan()[0]

    def test_quoted_values_and_windows_path_are_preserved(self):
        self.post.write_text('---\ntitle: "标题"\ndate: "2026-11-12"\nslug: "my-post"\n'
                             'summary: "C:\\Users\\m\\notes"\n---\n\n正文', encoding='utf-8')
        plan, posts = build.make_build_plan()
        self.assertEqual(posts[0]['slug'], 'my-post')
        self.assertEqual(posts[0]['date'], '2026-11-12')
        self.assertIn(r'C:\Users\m\notes', plan.files[self.root / 'index.html'])
        self.assertNotIn('\x07', plan.files[self.root / 'index.html'])

    def test_invalid_date_fails_without_writing(self):
        self.post.write_text('---\ndate: 2026-02-30\n---\n正文', encoding='utf-8')
        before = self.snapshot()
        with self.assertRaisesRegex(build.BuildError, 'hello.md.*日期'):
            self.render()
        self.assertEqual(before, self.snapshot())

    def test_real_1970_date_is_valid(self):
        self.post.write_text('---\ndate: 1970-01-01\n---\n正文', encoding='utf-8')
        self.assertEqual(build.load_posts()[0]['date'], '1970-01-01')

    def test_duplicate_slugs_include_case_differences(self):
        self.write_post(extra='slug: same\n')
        self.write_post(extra='slug: SAME\n', name='another.md')
        before = self.snapshot()
        with self.assertRaisesRegex(build.BuildError, '相同的文章网址'):
            self.render()
        self.assertEqual(before, self.snapshot())

    def test_unsafe_slugs(self):
        for slug in ('../index', '..\\index', 'C:\\file', 'a/b', 'a b', 'con', 'NUL.txt', '..', 'a.', 'a?b'):
            with self.subTest(slug=slug), self.assertRaises(build.BuildError):
                build.validate_slug(slug)

    def test_invalid_minutes_are_rejected(self):
        for minutes in ('0', '-1', '²', 'abc'):
            self.write_post(extra='minutes: %s\n' % minutes)
            with self.subTest(minutes=minutes), self.assertRaisesRegex(build.BuildError, 'minutes'):
                self.render()

    def test_marker_errors_fail_without_writing(self):
        index = self.root / 'index.html'
        original = index.read_text(encoding='utf-8')
        start, end = '<!-- BUILD:POSTS:START -->', '<!-- BUILD:POSTS:END -->'
        for text in (original.replace(start, ''), original.replace(start, start + start),
                     original.replace(start, 'TEMP').replace(end, start).replace('TEMP', end)):
            index.write_text(text, encoding='utf-8')
            before = self.snapshot()
            with self.assertRaisesRegex(build.BuildError, 'BUILD:POSTS'):
                self.render()
            self.assertEqual(before, self.snapshot())

    def test_render_failure_does_not_modify_outputs(self):
        before = self.snapshot()
        with patch.object(build, 'render_post', side_effect=build.BuildError('模拟转换失败')):
            with self.assertRaises(build.BuildError):
                self.render()
        self.assertEqual(before, self.snapshot())

    def test_failed_commit_rolls_back_replaced_files(self):
        plan = self.render()
        before = self.snapshot()
        real_replace = os.replace
        count = 0

        def fail_second_new(src, dst):
            nonlocal count
            if Path(src).name.startswith('new-'):
                count += 1
                if count == 2:
                    raise PermissionError('模拟文件占用')
            return real_replace(src, dst)

        with patch.object(build.os, 'replace', side_effect=fail_second_new):
            with self.assertRaisesRegex(build.BuildError, '已恢复原文件'):
                plan.commit()
        self.assertEqual(before, self.snapshot())

    def test_failed_delete_also_rolls_back_writes(self):
        old = self.root / 'posts/old.html'
        old.write_text('旧页面', encoding='utf-8')
        plan = self.render()
        before = self.snapshot()
        real_unlink = Path.unlink

        def fail_old(path, *args, **kwargs):
            if path == old:
                raise PermissionError('模拟旧文件无法删除')
            return real_unlink(path, *args, **kwargs)

        with patch.object(Path, 'unlink', fail_old):
            with self.assertRaises(build.BuildError):
                plan.commit()
        self.assertEqual(before, self.snapshot())

    def test_successful_build_is_repeatable_and_check_is_read_only(self):
        self.render().commit()
        plan = self.render()
        self.assertEqual(plan.changes(), [])
        before = self.snapshot()
        self.assertEqual(build.check_site(plan), [])
        self.assertEqual(before, self.snapshot())

    def test_full_text_search_includes_article_end_and_code(self):
        self.write_post(body='很长的正文' * 500 + '\n\n独一无二的结尾\n\n```js\nprefers-reduced-motion\n```')
        text = self.render().files[self.root / 'js/search-index.js']
        data = json.loads(text.split('window.__SEARCH_INDEX__ = ', 1)[1].strip().rstrip(';'))
        self.assertIn('独一无二的结尾', data[0]['b'])
        self.assertIn('prefers-reduced-motion', data[0]['b'])

    def test_symbol_tags_have_distinct_pages(self):
        self.write_post(extra='tags: C, C++, C#, index, AI, ai\n')
        plan, posts = build.make_build_plan()
        self.assertEqual(len(posts[0]['tags']), 5)
        slugs = [build.tag_slug(t) for t in posts[0]['tags']]
        self.assertEqual(len(set(slugs)), 5)
        self.assertNotIn('index', slugs)
        for slug in slugs:
            self.assertIn(self.root / 'tags' / (slug + '.html'), plan.files)

    def test_removing_all_tags_cleans_old_tag_pages(self):
        self.render().commit()
        self.write_post(extra='tags:\n')
        plan = self.render()
        self.assertIn(self.root / 'tags/随笔.html', plan.deletes)
        plan.commit()
        self.assertTrue((self.root / 'tags/index.html').exists())
        self.assertFalse((self.root / 'tags/随笔.html').exists())
        self.assertEqual(build.check_site(self.render()), [])

    def test_check_detects_missing_images_and_fragments(self):
        self.write_post(body='![图片](missing.png)\n\n[段落](#不存在)')
        errors = build.check_site(self.render(), include_stale=False)
        self.assertTrue(any('missing.png' in e for e in errors))
        self.assertTrue(any('不存在的段落' in e for e in errors))

    def test_check_detects_wrong_filename_case(self):
        self.write_post(body='[样式](../CSS/style.css)')
        self.assertTrue(any('CSS/style.css' in e for e in build.check_site(self.render(), False)))

    def test_check_reports_stale_outputs(self):
        self.assertTrue(any('尚未同步' in e for e in build.check_site(self.render())))

    def test_asset_version_changes_with_file_contents(self):
        first = self.render().files[self.root / 'about.html']
        stylesheet = self.root / 'css/style.css'
        stylesheet.write_text(stylesheet.read_text(encoding='utf-8') + '\n/* 更新 */\n', encoding='utf-8')
        second = self.render().files[self.root / 'about.html']
        pattern = r'href="(css/style\.css\?[^\"]+)"'
        self.assertNotEqual(re.search(pattern, first)[1], re.search(pattern, second)[1])

    def test_asset_version_uses_newly_generated_script(self):
        plan = build.BuildPlan()
        script = 'window.__SEARCH_INDEX__ = [];\n'
        plan.write(self.root / 'js/search-index.js', script)
        text = '<script src="js/search-index.js?mode=full&amp;v=old"></script>'
        result = build.version_local_assets(self.root / 'about.html', text, plan)
        url = unescape(re.search(r'src="([^\"]+)"', result)[1])
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query['mode'], ['full'])
        self.assertEqual(query['v'], [hashlib.sha256(script.encode('utf-8')).hexdigest()[:12]])

    def test_about_has_safe_html_fallback(self):
        names, hints = [], []

        class FallbackParser(HTMLParser):
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'p' and 'data-name' in attrs:
                    names.append(attrs)
                if 'alias-hint' in attrs.get('class', '').split():
                    hints.append(attrs)

        FallbackParser().feed((self.root / 'about.html').read_text(encoding='utf-8'))
        self.assertTrue(names)
        self.assertEqual(sum('hidden' not in attrs for attrs in names), 1)
        self.assertTrue(hints and all('hidden' in attrs for attrs in hints))

    def test_cli_build_alias_and_check(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
        for command in ('build', 'check'):
            result = subprocess.run([sys.executable, '-B', str(self.root / 'build.py'), command],
                                    capture_output=True, text=True, encoding='utf-8', env=env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.root / 'posts/hello.html').exists())

    def test_cli_failure_is_nonzero(self):
        self.write_post(extra='date: 错误日期\n')
        result = subprocess.run([sys.executable, '-B', str(self.root / 'build.py'), 'check'],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('hello.md', result.stderr)

    def test_url_change_failure_preserves_config_and_pages(self):
        index = self.root / 'index.html'
        index.write_text(index.read_text(encoding='utf-8').replace('<!-- BUILD:POSTS:START -->', ''), encoding='utf-8')
        before = self.snapshot()
        old_url = build.SITE['url']
        with patch.object(build, '__file__', str(self.root / 'build.py')):
            with self.assertRaises(build.BuildError):
                build.cmd_url('https://example.com/blog')
        self.assertEqual(build.SITE['url'], old_url)
        self.assertEqual(before, self.snapshot())

    def test_xml_urls_escape_ampersands(self):
        with patch.dict(build.SITE, {'url': 'https://example.com/a&b'}):
            plan = self.render()
            self.assertIn('a&amp;b', plan.files[self.root / 'feed.xml'])
            self.assertFalse(any('格式不正确' in error for error in build.check_site(plan, False)))

    def test_check_detects_invalid_xml(self):
        plan = self.render()
        plan.files[self.root / 'feed.xml'] = '<rss>'
        self.assertTrue(any('feed.xml 格式不正确' in error for error in build.check_site(plan, False)))

    def test_preview_serves_memory_and_reloads_without_writing_html(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
        process = subprocess.Popen([sys.executable, '-B', str(self.root / 'build.py'), 'preview',
                                    '--port', '0', '--no-browser'], stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding='utf-8', env=env,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        lines = queue.Queue()
        reader = threading.Thread(target=lambda: [lines.put(line) for line in process.stdout], daemon=True)
        reader.start()
        try:
            deadline = time.monotonic() + 15
            address = None
            while time.monotonic() < deadline:
                line = lines.get(timeout=15)
                match = re.search(r'http://127\.0\.0\.1:\d+/', line)
                if match:
                    address = match[0]
                    break
            self.assertIsNotNone(address)

            def get(route):
                with urlopen(address + route, timeout=3) as response:
                    return response.read().decode('utf-8')

            self.assertIn('data-muroj-preview', get('posts/hello.html'))
            self.assertFalse((self.root / 'posts/hello.html').exists())
            version = get('__muroj_preview_version')
            time.sleep(0.6)
            self.write_post(body='自动刷新后的内容')
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline and get('__muroj_preview_version') == version:
                time.sleep(0.15)
            self.assertIn('自动刷新后的内容', get('posts/hello.html'))
            self.assertFalse((self.root / 'posts/hello.html').exists())
        finally:
            process.terminate()
            process.communicate(timeout=8)
            reader.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
