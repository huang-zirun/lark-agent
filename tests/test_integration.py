import json
from devflow.intake.lark_cli import fetch_doc_source

def test_fetch():
    test_doc_url = "https://jcneyh7qlo8i.feishu.cn/wiki/AXWfwNtB6ieF7tk5o4acjJQknvh?from=from_copylink"
    print(f"Testing fetch for: {test_doc_url}")
    try:
        source = fetch_doc_source(test_doc_url)
        print("Fetch successful!")
        print(f"Title: {source.title}")
        print(f"Content length: {len(source.content)}")
        print(f"Identity: {source.identity}")
        # print(f"Content preview: {source.content[:200]}...")
    except Exception as e:
        print(f"Fetch failed: {e}")

if __name__ == "__main__":
    test_fetch()
