"""
SCHEMA INDEXER — Vector Search bằng ChromaDB (Bước 2)
Kỹ thuật RAG #1 (Parent-Child Retrieval): Nhúng từng Cột (Child) thành vector.
Kỹ thuật RAG #3 (Local Fallback): Cohere lỗi → chuyển sang offline model.
Kỹ thuật RAG #4 (Adaptive Reranking): Score cao → trả luôn, thấp → gọi Cohere Rerank.

[ĐÃ VÁ 3 ĐIỂM YẾU]:
1. Chuyển sang Cosine Similarity → Score chuẩn 0-1.
2. Mô tả ngữ nghĩa giàu hơn khi nhúng cột.
3. Sửa lỗi format document cho Cohere Rerank.
"""
import chromadb
import os
from typing import List, Dict, Any

from core.logger import get_logger
from core.llm_providers import LLMProvider
from modules.schema.engine import SchemaEngine
from modules.data_source.base import DataConnector

logger = get_logger(__name__)

# Tên collection trong ChromaDB (giống tên "bảng" trong DB vector)
COLLECTION_NAME = "schema_columns"


class SchemaIndexer:
    """
    Bộ não tìm kiếm ngữ nghĩa (Semantic Search) cho Schema.
    Nhúng từng cột trong DB thành vector, khi người dùng hỏi câu hỏi,
    tìm ra các bảng liên quan nhất thay vì đưa toàn bộ schema.
    """

    def __init__(self, connector: DataConnector):
        self.connector = connector
        self.engine = SchemaEngine(connector)
        
        # Khởi tạo ChromaDB (Lưu cố định xuống ổ cứng để tiết kiệm tiền gọi API Embedding)
        # Đường dẫn: AI_Analytics_Assistant/data/chroma_db
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        db_path = os.path.join(base_dir, "data", "chroma_db")
        os.makedirs(db_path, exist_ok=True)
          
        self._chroma_client = chromadb.PersistentClient(path=db_path) # mở cổng kết nối vào vector DB (ChromaDB).
        self._collection = None # lấy ra collection column để sử dụng.
        self._embedding_model = None # lấy ra embedding model.
        self._is_indexed = False # check xem đã index chưa.
        
        # [ĐỌc YAML 1 LẦN DUY NHẤT] Thay vì mở file 46 lần trong _build_rich_description()
        try:
            import yaml
            config_path = os.path.join(base_dir, "config", "schema_config.yaml")
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            self._column_descriptions = config.get("column_descriptions", {})
            logger.info(f"Schema Indexer: Đã nạp {len(self._column_descriptions)} mô tả cột từ schema_config.yaml.")
        except Exception as e:
            logger.warning(f"Không đọc được schema_config.yaml: {e}. Dùng mô tả rỗng.")
            self._column_descriptions = {}
        
        # [CACHE] Lưu kết quả schema đã profiled & relations để không gọi lại DB mỗi lần user hỏi
        self._cached_profiled_schema = None
        self._cached_relations = None
 
    def _get_embedding_model(self):
        """
        Lấy Embedding Model (Kỹ thuật RAG #3: Local Fallback).
        Ưu tiên Cohere Multilingual → Nếu lỗi → Chuyển sang offline model.
        """
        if self._embedding_model:
            return self._embedding_model
            
        try:
            self._embedding_model = LLMProvider.get_embedding_model()
            logger.info("Embedding: Đang dùng Cohere Multilingual v3 (Online).")
        except Exception as e:
            logger.warning(f"Cohere Embedding lỗi: {e}. Chuyển sang Local Fallback...")
            self._embedding_model = LLMProvider.get_fallback_embedding_model()
            logger.info("Embedding: Đang dùng all-MiniLM-L6-v2 (Offline).")
        
        return self._embedding_model

    def _build_rich_description(self, table_name: str, col_name: str, col_type: str, sample_values=None) -> str:
        """
        [VÁ #2] Tạo mô tả ngữ nghĩa GIÀU hơn cho mỗi cột.
        Thêm mô tả nghiệp vụ bằng tiếng Việt để Embedding hiểu ngữ cảnh tốt hơn.
        """
        # Sử dụng self._column_descriptions (đã đọc 1 lần trong __init__)
        COLUMN_DESCRIPTIONS = self._column_descriptions
        
        # Tạo mô tả cơ bản
        desc = f"Bảng {table_name}, Cột {col_name} ({col_type})"
        
        # Thêm mô tả nghiệp vụ nếu có
        col_key = col_name.lower()
        if col_key in COLUMN_DESCRIPTIONS:
            desc += f". Ý nghĩa: {COLUMN_DESCRIPTIONS[col_key]}"
        
        # Thêm giá trị mẫu nếu có
        if sample_values:
            desc += f". Giá trị mẫu: {sample_values}"
        
        return desc

    def index_schema(self) -> int:
        """
        Kỹ thuật RAG #1 (Parent-Child Retrieval):
        Nhúng từng CỘT (Child) thành 1 vector riêng lẻ.
        Metadata ghi rõ cột đó thuộc BẢNG (Parent) nào.
        
        [VÁ #1] Dùng Cosine Similarity thay vì L2 Distance.
        [VÁ #2] Mô tả ngữ nghĩa giàu hơn.
        """
        if self._is_indexed:
            logger.info("Schema đã được index trước đó. Bỏ qua.")
            return 0
        
        # Xóa collection cũ nếu tồn tại (để re-index sạch)
        try:
            self._chroma_client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
        
        # [VÁ #1] Tạo collection với Cosine Similarity (Score từ 0→1 chuẩn xác)
        self._collection = self._chroma_client.create_collection(
            name=COLLECTION_NAME,
            metadata={
                "description": "Schema columns for RAG retrieval",
                "hnsw:space": "cosine"  # ← THAY ĐỔI: Dùng Cosine thay vì L2 (Euclidean)
            }
        )
        
        # Lấy schema từ Engine (đã qua Column Pruning + Profiling)
        raw_schema = self.connector.get_schema()
        pruned_schema = self.engine.prune_columns(raw_schema)
        profiled_schema = self.engine.profile_columns(pruned_schema)
        
        # [VÁ #7] Bóc tách FK từ Engine (3 tầng: DB Metadata → Naming Conv → JSON Fallback)
        all_relations = self.engine.detect_relationships()
        
        # Xây bảng tra cứu nhanh: column → FK reference
        # Ví dụ: ("Fact_Sales", "CustomerKey") → "Dim_Customers.CustomerKey"
        fk_lookup = {}
        pk_set = set()  # Tập hợp các cột là PK (đầu nhận của FK)
        for rel in all_relations:
            from_key = (rel["from_table"], rel["from_column"])
            to_key = (rel["to_table"], rel["to_column"])
            fk_lookup[from_key] = f"{rel['to_table']}.{rel['to_column']}"
            pk_set.add(to_key)
        
        logger.info(f"Schema Indexer: Đã map {len(fk_lookup)} FK + {len(pk_set)} PK vào Metadata.")
        
        # Chuẩn bị dữ liệu để nhúng
        documents = []
        metadatas = []
        ids = []
        
        for table in profiled_schema:
            t_name = table["table_name"]
            for col in table["columns"]:
                c_name = col["name"]
                c_type = str(col["type"])
                samples = col.get("sample_values", None)
                
                # [VÁ #2] Tạo mô tả ngữ nghĩa GIÀU (có cả từ khóa tiếng Việt)
                doc_text = self._build_rich_description(t_name, c_name, c_type, samples)
                
                # [VÁ #7] Xác định vai trò FK/PK của cột này
                col_key = (t_name, c_name)
                is_fk = col_key in fk_lookup
                is_pk = col_key in pk_set
                fk_ref = fk_lookup.get(col_key, "")  # Trống nếu không phải FK
                
                documents.append(doc_text)
                metadatas.append({
                    "table_name": t_name,
                    "column_name": c_name,
                    "column_type": c_type,
                    "is_primary_key": is_pk,
                    "is_foreign_key": is_fk,
                    "fk_references": fk_ref  # VD: "Dim_Customers.CustomerKey"
                })
                ids.append(f"{t_name}.{c_name}")
        
        if not documents:
            logger.warning("Không có cột nào để index!")
            return 0
        
        # Nhúng vector bằng Embedding Model
        embedding_model = self._get_embedding_model()
        embeddings = embedding_model.embed_documents(documents)
        
        # Nạp vào ChromaDB
        self._collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        
        self._is_indexed = True
        logger.info(f"Schema Indexer: Đã nhúng {len(documents)} cột vào ChromaDB (Cosine Similarity).")
        return len(documents)

    def search_relevant_tables(self, question: str, top_k: int = 50) -> List[Dict[str, Any]]:
        """
        Tìm kiếm các bảng liên quan nhất đến câu hỏi của người dùng.
        [VÁ #4] Tăng top_k lên 50 cột (để gom được số lượng bảng lớn cho truy vấn phức tạp).
        [VÁ #1] Score dùng Cosine: 1 - (distance/2) cho ra range 0→1 chuẩn xác.
        """
        if not self._is_indexed or not self._collection:
            logger.warning("Chưa index schema! Gọi index_schema() trước.")
            return []
        
        # Nhúng câu hỏi thành vector
        embedding_model = self._get_embedding_model()
        query_embedding = embedding_model.embed_query(question)
        
        # Tìm kiếm trong ChromaDB
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count()),
            include=["documents", "metadatas", "distances"]
        )
        
        if not results["ids"][0]:
            return []
        
        # Gom kết quả theo bảng (Parent), loại trùng
        table_scores = {}
        for i, doc_id in enumerate(results["ids"][0]):
            metadata = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            
            # [VÁ #1] Cosine distance nằm trong khoảng [0, 2]
            # 0 = giống hệt, 2 = ngược hoàn toàn
            # Chuyển thành score: 1 - (distance / 2) → range [0, 1]
            score = max(0, 1 - (distance / 2))
            
            t_name = metadata["table_name"]
            if t_name not in table_scores:
                table_scores[t_name] = {
                    "table_name": t_name,
                    "score": score,
                    "matched_columns": []
                }
            
            # Luôn lấy score cao nhất cho mỗi bảng
            if score > table_scores[t_name]["score"]:
                table_scores[t_name]["score"] = score
                
            table_scores[t_name]["matched_columns"].append({
                "column": metadata["column_name"],
                "type": metadata["column_type"],
                "score": round(score, 4)
            })
        
        # Sắp xếp theo điểm giảm dần
        sorted_tables = sorted(table_scores.values(), key=lambda x: x["score"], reverse=True)
        
        logger.info(f"Schema Search: Câu hỏi '{question[:50]}...' → Tìm thấy {len(sorted_tables)} bảng liên quan.")
        return sorted_tables

    def adaptive_rerank(self, question: str, search_results: List[Dict]) -> List[Dict]:
        """
        Kỹ thuật RAG #4 (Adaptive Reranking):
        - Score Top 1 >= 0.7 → Tin tưởng kết quả, trả luôn.
        - Score Top 1 < 0.7 → Gọi Cohere Rerank để lọc chính xác hơn.
        """
        if not search_results:
            return []
        
        top_score = search_results[0]["score"]
        
        # [VÁ #5] Hàm tiện ích: Lọc theo "Ngưỡng Tương Đối" (Relative Threshold)
        def _filter_results(results):
            if not results:
                return []
            
            # Tính ngưỡng dựa vào điểm cao nhất của danh sách truyền vào
            current_top_score = results[0]["score"]
            
            # Ngưỡng động: Lấy điểm cao nhất trừ đi 0.15.
            # Giới hạn đáy là 0.5 để rác không lọt vào.
            dynamic_threshold = max(0.5, current_top_score - 0.15)
            
            filtered = [r for r in results if r["score"] >= dynamic_threshold]
            
            # Nếu lọc xong mà không còn bảng nào, thì trả về top 3 bảng an toàn
            if not filtered:
                return results[:3]
            # Giới hạn an toàn tuyệt đối là 7 bảng để AI không bị quá tải
            return filtered[:7]
            
        # [VÁ #6] Nâng bypass threshold lên 0.85. 
        # Vì điểm Cosine hiếm khi dưới 0.6, để 0.7 thì hệ thống lười không chịu gọi Rerank.
        if top_score >= 0.85:
            logger.info(f"Adaptive Rerank: Score Top 1 = {top_score:.4f} >= 0.85 → BỎ QUA Rerank (Tiết kiệm API).")
            return _filter_results(search_results)
        
        # Nếu score < 0.85 → Gọi Cohere Rerank để chấm điểm lại gắt gao hơn
        try:
            logger.info(f"Adaptive Rerank: Score Top 1 = {top_score:.4f} < 0.85 → GỌI Cohere Rerank.")
            reranker = LLMProvider.get_reranker_model()
            
            # [VÁ #3] Chuẩn bị documents cho Reranker (đảm bảo không rỗng)
            docs_for_rerank = []
            valid_results = []
            for result in search_results:
                cols_list = [c["column"] for c in result["matched_columns"]]
                cols_text = ", ".join(cols_list) if cols_list else result["table_name"]
                doc_text = f"Bảng {result['table_name']} chứa các cột: {cols_text}"
                
                if doc_text.strip():
                    docs_for_rerank.append(doc_text)
                    valid_results.append(result)
            
            if not docs_for_rerank:
                logger.warning("Không có document hợp lệ để Rerank.")
                return _filter_results(search_results)
            
            from langchain_core.documents import Document
            reranked = reranker.compress_documents(
                documents=[Document(page_content=d) for d in docs_for_rerank],
                query=question
            )
            
            # Cập nhật thứ tự và ĐIỂM SỐ dựa trên kết quả Rerank
            reranked_results = []
            for doc in reranked:
                table_name = doc.page_content.split(" chứa các cột:")[0].replace("Bảng ", "").strip()
                for result in valid_results:
                    if result["table_name"] == table_name and result not in reranked_results:
                        # [VÁ #6] Phải đè điểm cũ (Cosine) bằng điểm mới cực sắc nét của Reranker!
                        if "relevance_score" in doc.metadata:
                            result["score"] = doc.metadata["relevance_score"]
                        reranked_results.append(result)
                        break
            
            logger.info(f"Rerank hoàn tất: {len(reranked_results)} bảng sau khi lọc.")
            return _filter_results(reranked_results) if reranked_results else _filter_results(search_results)
            
        except Exception as e:
            logger.warning(f"Cohere Rerank lỗi: {e}. Trả về kết quả gốc.")
            return _filter_results(search_results)

    def get_relevant_schema_for_prompt(self, question: str) -> str:
        """
        Hàm chính Pipeline Bước 2: Câu hỏi → Search → Rerank → Trả về schema liên quan.
        Kết quả là đoạn text sẵn sàng nhét vào Prompt cho AI.
        """
        # 1. Tìm kiếm các bảng liên quan
        search_results = self.search_relevant_tables(question)
        
        # 2. Adaptive Rerank
        final_results = self.adaptive_rerank(question, search_results)
        
        if not final_results:
            # Fallback: Nếu không tìm thấy gì, trả về toàn bộ schema
            logger.warning("Không tìm thấy bảng liên quan. Trả về toàn bộ schema.")
            return self.engine.build_context()
        
        # 3. Lấy tên các bảng liên quan
        relevant_table_names = [r["table_name"] for r in final_results]
        
        # 4. [CACHE] Dùng cache thay vì gọi lại DB 3 lần mỗi câu hỏi
        if self._cached_profiled_schema is None:
            raw_schema = self.connector.get_schema()
            pruned_schema = self.engine.prune_columns(raw_schema)
            self._cached_profiled_schema = self.engine.profile_columns(pruned_schema)
            self._cached_relations = self.engine.detect_relationships()
            logger.info("Schema Indexer: Đã cache profiled_schema & relations (lần đầu).")
        
        # Lọc chỉ giữ bảng liên quan
        filtered_schema = [t for t in self._cached_profiled_schema if t["table_name"] in relevant_table_names]
        
        # 5. Lấy quan hệ (chỉ giữ quan hệ liên quan đến các bảng được chọn)
        filtered_relations = [
            r for r in self._cached_relations
            if r["from_table"] in relevant_table_names or r["to_table"] in relevant_table_names
        ]
        
        # 6. Format thành text cho Prompt
        result = self.engine.format_schema_for_prompt(filtered_schema, filtered_relations)
        
        logger.info(f"Schema Indexer: Trả về {len(filtered_schema)}/{len(self._cached_profiled_schema)} bảng liên quan cho câu hỏi.")
        return result
