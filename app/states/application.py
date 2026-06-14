from aiogram.fsm.state import State, StatesGroup


class ApplicationForm(StatesGroup):
    waiting_uid = State()
    waiting_register_photo = State()
    waiting_deposit_photo = State()
