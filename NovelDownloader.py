import argparse
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import time

class NovelDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
        self.visited_urls = set()
        self.current_chapter = None
        self.chapter_content = []
        self.chapter_count = 0

    def clean_chapter_title(self, title):
        """清理章节标题中的分页信息"""
        # 去除括号内容（如"第一章 (2/3)" → "第一章"）
        title = re.sub(r"\(.*?\)|（.*?）|【.*?】", "", title)
        # 去除页码标记（如"第一章 - 第2页" → "第一章"）
        title = re.sub(r"[-—]\s*第?[0-9]+[页章節]?", "", title)
        # 去除首尾空白
        return title.strip()

    def extract_chapter_title(self, soup):
        """提取章节标题"""
        # 优先从<h1>标签获取
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            title = h1.get_text(strip=True)
            return self.clean_chapter_title(title)
        
        # 次选从<title>获取
        if soup.title:
            title = soup.title.get_text(strip=True)
            # 去除网站名部分（如"第一章 - 某某小说网"）
            title = re.split(r"[-|_|—]", title)[0].strip()
            return self.clean_chapter_title(title)
        
        return "未命名章节"

    def extract_main_content(self, soup):
        """提取正文内容"""
        # 常见正文选择器（按优先级尝试）
        selectors = [
            {"name": "div", "id": "content"},
            {"name": "div", "class": "content"},
            {"name": "div", "id": "chapter-content"},
            {"name": "div", "class": "chapter-content"},
            {"name": "article"},
            {"name": "div", "class": re.compile(r"read|text|article")},
            {"name": "div", "id": re.compile(r"content|chapter")},
        ]
        
        for selector in selectors:
            content = soup.find(**selector)
            if content and len(content.get_text(strip=True)) > 100:
                # 清理不需要的元素
                for elem in content.find_all(["script", "style", "div.ad", "ins", "iframe"]):
                    elem.decompose()
                return content.get_text("\n", strip=True)
        
        return None

    def extract_next_page(self, soup, current_url):
        """提取下一页链接"""
        # 1. 查找包含下一页关键词的链接
        next_keywords = ["下一页", "下一章", "下一节", "下一頁", "Next", ">", "›"]
        for keyword in next_keywords:
            next_link = soup.find("a", string=re.compile(fr"^{keyword}$", flags=re.IGNORECASE))
            if next_link and next_link.get("href"):
                return next_link["href"]
        
        # 2. 查找常见分页class的链接
        for class_name in ["next", "next-page", "pagination-next"]:
            next_link = soup.find("a", class_=class_name)
            if next_link and next_link.get("href"):
                return next_link["href"]
        
        # 3. 分析URL规律（如/page/2 → /page/3）
        if "page" in current_url.lower():
            match = re.search(r"(page|p)=(\d+)", current_url, re.IGNORECASE)
            if match:
                next_num = int(match.group(2)) + 1
                return current_url.replace(
                    f"{match.group(1)}={match.group(2)}", 
                    f"{match.group(1)}={next_num}"
                )
        
        return None

    def process_page(self, url, output_file):
        """处理单个页面"""
        if url in self.visited_urls:
            return True
        
        self.visited_urls.add(url)
        # print(f"处理: {url}")
        
        try:
            # 请求页面
            time.sleep(1)  # 礼貌性延迟
            response = self.session.get(url, timeout=10)
            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 提取信息
            chapter_title = self.extract_chapter_title(soup)
            content = self.extract_main_content(soup)
            
            if not content:
                print(f"⚠️ 未找到正文内容: {url}")
                return False
            
            # 检查是否是新章节
            if chapter_title != self.current_chapter:
                self.save_current_chapter(output_file)
                self.current_chapter = chapter_title
                self.chapter_content = []
                self.chapter_count += 1
            
            # 添加内容
            self.chapter_content.append(content)
            
            # 获取下一页
            next_page = self.extract_next_page(soup, url)
            if next_page and not next_page.startswith(("http://", "https://")):
                next_page = urljoin(url, next_page)
            
            return next_page
        
        except Exception as e:
            print(f"❌ 处理失败: {url} - {str(e)}")
            return False

    def save_current_chapter(self, output_file):
        """保存当前章节内容"""
        if not self.current_chapter or not self.chapter_content:
            return
        
        with open(output_file, "a", encoding="utf-8") as f:
            # 写入章节标题
            f.write(f"{self.current_chapter}\n")
            # 写入章节内容
            f.write("".join(self.chapter_content) + "\n")
        
        print(f"✅ 已保存章节: {self.current_chapter}")

    def download_novel(self, start_url, output_file="novel.txt"):
        """下载小说并合并章节"""
        # 清空或创建输出文件
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("")
        
        current_url = start_url
        while current_url:
            current_url = self.process_page(current_url, output_file)
        
        # 保存最后一章
        self.save_current_chapter(output_file)
        print(f"\n🎉 下载完成！共 {self.chapter_count} 章，已保存到 {output_file}")


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='NovelDownloader',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    
    parser.add_argument(
        '-u', '--url',
        required=True,
        help='起始章节URL（必须）',
        metavar='URL'
    )
    parser.add_argument(
        '-o', '--output',
        default='novel.txt',
        help='输出文件路径',
        metavar='FILE'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=10,
        help='请求超时时间（秒）'
    )
    
    return parser.parse_args()

def main():
    # 解析参数
    args = parse_arguments()
    
    # 开始下载
    start_time = time.time()
    print(f"开始下载: {args.url}")
    print(f"输出文件: {args.output}")
    
    try:
        nd = NovelDownloader()
        nd.download_novel(
            start_url=args.url,
            output_file=args.output
        )
    except KeyboardInterrupt:
        print("\n用户中断，正在保存已下载内容...")
    except Exception as e:
        print(f"\n发生错误: {str(e)}")
    finally:
        print(f"总耗时: {time.time() - start_time:.2f}秒")


if __name__ == "__main__":
    main()