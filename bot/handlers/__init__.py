from aiogram import Router

from . import (
    add_catcher,
    catcher_actions,
    catchers,
    channels,
    cmds,
    global_back,
    ignores,
    profile,
    renew_sub,
    start_stop,
    triggers,
)

router = Router()
router.include_router(profile.router)
router.include_router(start_stop.router)
router.include_router(triggers.router)
router.include_router(ignores.router)
router.include_router(renew_sub.router)

router.include_router(catchers.router)
router.include_router(catcher_actions.router)
router.include_router(add_catcher.router)
router.include_router(channels.router)

router.include_router(cmds.router)
router.include_router(global_back.router)
