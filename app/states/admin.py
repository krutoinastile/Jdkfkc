from aiogram.fsm.state import State, StatesGroup


class AdminSearchForm(StatesGroup):
    waiting_query = State()
