from aiogram.fsm.state import State, StatesGroup


class CalculatorStates(StatesGroup):
    waiting_amount = State()
