from .chat import router as chat_router
from .news import router as news_router
from .user_info import router as user_info_router
from .message import router as message_router

all_routers = [
    chat_router,
    news_router,
    user_info_router,
    message_router,
]