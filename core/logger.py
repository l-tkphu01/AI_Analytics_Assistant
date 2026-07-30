import logging
import sys
import os # Thêm thư viện này
from config.settings import settings
 
def get_logger(name: str) -> logging.Logger:
    """Khởi tạo và cấu hình logger."""
    logger = logging.getLogger(name)
    
    # Chỉ add handler nếu logger chưa có handler nào (tránh duplicate log)
    if not logger.handlers:
        logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
        
        # Tạo định dạng chung
        formatter = logging.Formatter( 
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 1. Console handler (In ra màn hình)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # 2. File handler (Lưu ra file, giới hạn dung lượng để không bị tràn)
        os.makedirs("logs", exist_ok=True) # Tự tạo thư mục logs nếu chưa có
        from logging.handlers import RotatingFileHandler
        # Giới hạn 5MB mỗi file, giữ tối đa 3 file cũ (app.log, app.log.1, app.log.2, app.log.3)
        file_handler = RotatingFileHandler("logs/app.log", maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
    return logger
