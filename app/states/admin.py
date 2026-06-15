from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    broadcast = State()
    edit_setting = State()
    billing_token = State()
    billing_price = State()
