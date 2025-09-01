from aiogram.fsm.state import State, StatesGroup


class UserState(StatesGroup):
    actions = State()


class InfoTriggersState(StatesGroup):
    info = State()
    add = State()
    delete = State()


class InfoIgnoresState(StatesGroup):
    info = State()
    add = State()
    delete = State()


class UserAdminState(StatesGroup):
    enter_api_id = State()
    enter_api_hash = State()
    enter_phone = State()
    enter_code = State()
    enter_password = State()


class CatcherState(StatesGroup):
    actions = State()


class InfoChannelsState(StatesGroup):
    info = State()
    add = State()
    delete = State()
