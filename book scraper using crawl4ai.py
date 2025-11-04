import asyncio
from crawl4ai import AsyncWebCrawler
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

async def scrape_chapter(url, chapter_number, crawler):
    """
    Scrape a single chapter
    
    Args:
        url (str): Chapter URL
        chapter_number (int): Chapter number
        crawler: AsyncWebCrawler instance
    
    Returns:
        dict: Chapter data
    """
    try:
        print(f" Scraping Chapter {chapter_number}...")
        
        result = await crawler.arun(
            url=url,
            wait_for="css:body",
            delay_before_return_html=1.5
        )
        
        if result.success:
            soup = BeautifulSoup(result.html, 'html.parser')
            
            # Extract chapter title
            title = ""
            title_elem = soup.find('h1') or soup.find('h2', class_='entry-title')
            if title_elem:
                title = title_elem.get_text(strip=True)
            
            # Remove unwanted elements before extracting content
            for elem in soup.find_all(['div', 'section', 'form'], class_=lambda x: x and any(
                keyword in str(x).lower() for keyword in ['login', 'signup', 'sign-up', 'register', 'auth']
            )):
                elem.decompose()
            
            # Remove images
            for img in soup.find_all('img'):
                img.decompose()
            
            # Remove navigation, footer, sidebar
            for elem in soup.find_all(['nav', 'footer', 'aside', 'header']):
                elem.decompose()
            
            # Remove social share buttons
            for elem in soup.find_all(class_=lambda x: x and any(
                keyword in str(x).lower() for keyword in ['share', 'social', 'comment']
            )):
                elem.decompose()
            
            # Extract main content
            content_selectors = [
                'article',
                '.entry-content',
                '.post-content',
                '.book-content',
                'main',
                '#content'
            ]
            
            text_content = ""
            for selector in content_selectors:
                main_content = soup.select_one(selector)
                if main_content:
                    paragraphs = main_content.find_all(['p', 'div', 'h2', 'h3', 'h4'])
                    text_parts = []
                    
                    for p in paragraphs:
                        text = p.get_text(strip=True)
                        if text:
                            # Stop if we encounter content-ending keywords
                            text_lower = text.lower()
                            if any(keyword in text_lower for keyword in [
                                'পরবর্তী অধ্যায়', 'next chapter', 'আরও পড়ুন', 'read more',
                                'লগইন', 'login', 'সাইন আপ', 'sign up', 'রেজিস্টার'
                            ]):
                                break
                            text_parts.append(text)
                    
                    text_content = '\n\n'.join(text_parts)
                    break
            
            if not text_content and hasattr(result, 'markdown'):
                text_content = result.markdown
                # Remove login/signup text from markdown
                lines = text_content.split('\n')
                filtered_lines = []
                for line in lines:
                    line_lower = line.lower()
                    if not any(keyword in line_lower for keyword in [
                        'login', 'sign up', 'register', 'লগইন', 'সাইন আপ'
                    ]):
                        filtered_lines.append(line)
                text_content = '\n'.join(filtered_lines)
            
            return {
                "chapter_number": chapter_number,
                "title": title,
                "url": url,
                "content": text_content,
                "content_length": len(text_content)
            }
        else:
            return {
                "chapter_number": chapter_number,
                "url": url,
                "error": "Failed to scrape chapter"
            }
            
    except Exception as e:
        return {
            "chapter_number": chapter_number,
            "url": url,
            "error": str(e)
        }

async def scrape_book_with_chapters(url):
    """
    Scrape book main page and all chapters
    
    Args:
        url (str): Book main page URL
    
    Returns:
        dict: Complete book data with all chapters
    """
    try:
        async with AsyncWebCrawler(verbose=False) as crawler:
            print(f"Scraping main page...")
            
            # Scrape main book page
            result = await crawler.arun(
                url=url,
                wait_for="css:body",
                delay_before_return_html=2.0
            )
            
            if not result.success:
                return {"error": "Failed to scrape main page", "url": url}
            
            soup = BeautifulSoup(result.html, 'html.parser')
            
            # Remove unwanted elements from main page
            for img in soup.find_all('img'):
                img.decompose()
            
            for elem in soup.find_all(['nav', 'footer', 'aside']):
                elem.decompose()
            
            for elem in soup.find_all(class_=lambda x: x and any(
                keyword in str(x).lower() for keyword in ['login', 'signup', 'share', 'comment']
            )):
                elem.decompose()
            
            # Extract book title
            page_title = ""
            title_elem = soup.find('h1') or soup.find('h2', class_='entry-title')
            if title_elem:
                page_title = title_elem.get_text(strip=True)
            
            if not page_title:
                title_tag = soup.find('title')
                if title_tag:
                    page_title = title_tag.get_text(strip=True)
            
            # Extract book details
            book_details = {"title": page_title}
            
            # author, publisher,
            meta_text = soup.get_text()
            if 'লেখক' in meta_text or 'author' in meta_text.lower():
                for elem in soup.find_all(['p', 'div', 'span']):
                    text = elem.get_text(strip=True)
                    if 'লেখক' in text or 'author' in text.lower():
                        book_details['author'] = text
                        break
            
            # links from main article/content 
            chapter_links = []
            base_domain = urlparse(url).netloc
            
            # the main content area
            main_content_area = None
            for selector in ['article', '.entry-content', '.post-content', '.book-content', 'main']:
                main_content_area = soup.select_one(selector)
                if main_content_area:
                    break
            
            # If no main content area found, use body
            if not main_content_area:
                main_content_area = soup.find('body')
            
            # Look for ALL internal links in the content area
            if main_content_area:
                for link in main_content_area.find_all('a', href=True):
                    href = link['href']
                    text = link.get_text(strip=True)
                    
                    # Skip empty links
                    if not text or not href:
                        continue
                    
                    # Convert relative URLs to absolute
                    full_url = urljoin(url, href)
                    link_domain = urlparse(full_url).netloc
                    
                    if link_domain == base_domain and full_url != url:
                        # Skip links
                        skip_keywords = ['login', 'signup', 'register', 'category', 'tag', 'author', 
                                       'search', 'cart', 'checkout', '#', 'javascript']
                        
                        if not any(keyword in full_url.lower() for keyword in skip_keywords):
                            chapter_links.append({
                                'url': full_url,
                                'text': text
                            })
            
            # Remove duplicates
            seen_urls = set()
            unique_chapters = []
            for chapter in chapter_links:
                if chapter['url'] not in seen_urls:
                    seen_urls.add(chapter['url'])
                    unique_chapters.append(chapter)
            
            print(f"\n Found {len(unique_chapters)} content links")
            
            # Show found links
            if unique_chapters:
                print("\n Content links found:")
                for i, link in enumerate(unique_chapters[:10], 1):  # Show first 10
                    print(f"  {i}. {link['text'][:60]}...")
                if len(unique_chapters) > 10:
                    print(f"  ... and {len(unique_chapters) - 10} more")
            
            # Scrape all chapters
            chapters_data = []
            skipped_count = 0
            
            if unique_chapters:
                print(f"\n Scraping {len(unique_chapters)} content pages...")
                for i, chapter_link in enumerate(unique_chapters, 1):
                    chapter_data = await scrape_chapter(chapter_link['url'], i, crawler)
                    
                    # length is sufficient or not
                    if 'error' not in chapter_data and chapter_data.get('content_length', 0) < 100:
                        print(f" Skipping Chapter {i} (too short: {chapter_data.get('content_length', 0)} chars)")
                        skipped_count += 1
                        continue
                    
                    chapters_data.append(chapter_data)
                    
                    # Show progress
                    if i % 5 == 0:
                        print(f" Scraped {len(chapters_data)}/{len(unique_chapters)} pages")
                    
                    await asyncio.sleep(1) 
                
                if skipped_count > 0:
                    print(f"\n Skipped {skipped_count} chapters (content length < 100 characters)")
            else:
                print("\n No content links found. Trying to scrape main page content...")
                # If no links found, scrape the main page itself as chapter 1
                chapter_data = await scrape_chapter(url, 1, crawler)
                if chapter_data.get('content_length', 0) >= 50:
                    chapters_data.append(chapter_data)
                else:
                    print(f" Main page content too short ({chapter_data.get('content_length', 0)} chars)")
            
            return {
                "url": url,
                "book_details": book_details,
                "total_chapters": len(chapters_data),
                "chapters": chapters_data
            }
            
    except Exception as e:
        return {"error": str(e), "url": url}

def save_to_markdown(data, filename="book_complete.md"):
    """Save complete book with all chapters to markdown"""
    with open(filename, 'w', encoding='utf-8') as f:
        # book title
        f.write(f"# {data['book_details'].get('title', 'Untitled Book')}\n\n")
        f.write("---\n\n")
        
        # all chapters (no table of contents, no extra info)
        for chapter in data['chapters']:
            if 'error' not in chapter:
                f.write(f"## {chapter['title']}\n\n")
                f.write(f"{chapter['content']}\n\n")
                f.write("---\n\n")
    
    print(f"Markdown saved to {filename}")

def save_to_json(data, filename="book_complete.json"):
    """Save complete data to JSON"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f" JSON saved to {filename}")

async def main():
    print("=" * 60)
    print(" Book Chapter Scraper")
    print("=" * 60)
    
    url = input("\nEnter the book main page URL: ").strip()
    
    if not url:
        print(" Error: Please provide a URL")
        return
    
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    print(f"\n Starting scraping process...\n")
    
    # Scrape book and all chapters
    data = await scrape_book_with_chapters(url)
    
    # result showing
    if "error" in data:
        print(f"\n Error: {data['error']}")
        return
    
    print("\n" + "=" * 60)
    print(" SCRAPING COMPLETE")
    print("=" * 60)
    print(f"\n Book: {data['book_details'].get('title', 'N/A')}")
    print(f" Total Chapters Scraped: {data['total_chapters']}")
    print(f" Valid Chapters (>100 chars): {len([c for c in data['chapters'] if 'error' not in c])}")
    
    if data['chapters']:
        print("\n Chapters:")
        for chapter in data['chapters']:
            if 'error' not in chapter:
                status = "ok" if chapter['content_length'] >= 100 else "x"
                print(f"  {status} {chapter['chapter_number']}. {chapter['title']} ({chapter['content_length']} chars)")
            else:
                print(f" {chapter['chapter_number']}. Error: {chapter['error']}")
    
    # Save files
   
    save_choice = input("Save to files? (y/n): ").strip().lower()
    
    if save_choice == 'y':
        md_filename = input("Markdown filename (default: bookname.md): ").strip()
        if not md_filename:
            md_filename = "book_complete.md"
        save_to_markdown(data, md_filename)
        
        json_filename = input("JSON filename (default: bookname.json): ").strip()
        if not json_filename:
            json_filename = "book_complete.json"
        save_to_json(data, json_filename)
        
        print("\n All files saved successfully")

if __name__ == "__main__":
    asyncio.run(main())
    