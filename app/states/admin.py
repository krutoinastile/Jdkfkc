from aiogram.fsm.state import State, StatesGroup


class AdminPaymentSettings(StatesGroup):
    edit_provider_token = State()
    edit_crypto_token = State()
    edit_price = State()
    edit_days = State()
    edit_crypto_asset = State()
