from embedders.embedder import get_chroma_client

try:
    client = get_chroma_client()
    
    collections = client.list_collections()
    print(f"현재 DB에 있는 컬렉션 목록: {[c.name for c in collections]}")
    
    collection = client.get_collection(name="kuriq_courses")
    print(f"kuriq_courses 컬렉션의 데이터 개수: {collection.count()}개")

except ValueError as e:
    print(f"에러: {e}")