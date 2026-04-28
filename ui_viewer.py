import streamlit as st
import pandas as pd
from embedders.embedder import get_chroma_client

st.set_page_config(layout="wide")
st.title("큐릭 크로마DB 뷰어")

try:
    client = chromadb.PersistentClient(path="./chroma_db")
    collection = client.get_collection(name="kuriq_courses")
    
    total_count = collection.count()
    st.success(f"현재 DB에 총 **{total_count}개**의 데이터가 있습니다.")

    limit = st.slider("몇 개까지 조회할까요?", min_value=10, max_value=1000, value=100, step=10)
    
    results = collection.get(limit=limit)
    
    if results['ids']:
        df = pd.DataFrame({
            "ID": results['ids'],
            "문서 (내용)": results['documents'],
            "메타데이터": [str(m) for m in results['metadatas']]
        })
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("가져올 데이터가 없습니다.")

except Exception as e:
    st.error(f"에러가 발생했습니다: {e}")