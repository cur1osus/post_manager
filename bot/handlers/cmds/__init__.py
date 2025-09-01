from . import start, reg_catcher, create_deep_link
from aiogram import Router

router = Router()
router.include_router(start.router)
router.include_router(reg_catcher.router)
router.include_router(create_deep_link.router)
