import dataclasses
import datetime
import decimal
import enum
import typing


_MoneyAmountTypes = typing.Union[int, float, decimal.Decimal]


class Money:
    minor_factor: int
    currency_code: str

    def __init__(
        self,
        value: _MoneyAmountTypes,
    ) -> None:
        self._value = value

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self._value!r})'

    @classmethod
    def from_minor(cls, value: _MoneyAmountTypes):
        return cls(value / cls.minor_factor)

    @property
    def minors(self) -> _MoneyAmountTypes:
        return int(self._value * self.minor_factor)

    @property
    def value(self) -> _MoneyAmountTypes:
        return self._value


class KZT(Money):
    currency_code = 'KZT'
    minor_factor = 100


class USD(Money):
    code = 'USD'
    minor_factor = 100


class EUR(Money):
    currency_code = 'EUR'
    minor_factor = 100


class RUB(Money):
    currency_code = 'RUB'
    minor_factor = 100


class AmountCategory(str, enum.Enum):
    FIXED = 'FIXED'
    RANGE = 'RANGE'


class DateCategory(str, enum.Enum):
    DAILY = 'DAILY'
    MONTHLY = 'MONTHLY'
    QUARTERLY = 'QUARTERLY'
    YEARLY = 'YEARLY'
    MANUAL = 'MANUAL'


class OrderStatus(str, enum.Enum):
    UNPAID = 'UNPAID'
    ON_HOLD = 'ON_HOLD'
    PAID = 'PAID'
    EXPIRED = 'EXPIRED'


class PaymentStatus(str, enum.Enum):
    PENDING = 'PENDING'
    REQUIRES_ACTION = 'REQUIRES_ACTION'
    APPROVED = 'APPROVED'
    CAPTURED = 'CAPTURED'
    CANCELLED = 'CANCELLED'
    DECLINED = 'DECLINED'


class RefundStatus(str, enum.Enum):
    PENDING = 'PENDING'
    APPROVED = 'APPROVED'
    DECLINED = 'DECLINED'


class CaptureMethod(str, enum.Enum):
    AUTO = 'AUTO'
    MANUAL = 'MANUAL'


class PayerType(str, enum.Enum):
    CARD = 'CARD'
    CARD_NO_CVC = 'CARD_NO_CVC'
    CARD_WITH_BINDING = 'CARD_WITH_BINDING'
    BINDING = 'BINDING'
    APPLE_PAY = 'APPLE_PAY'
    GOOGLE_PAY = 'GOOGLE_PAY'
    MASTERPASS = 'MASTERPASS'


class EventName(str, enum.Enum):
    ORDER_CREATED = 'ORDER_CREATED'
    PAYMENT_CREATED = 'PAYMENT_CREATED'
    REFUND_CREATED = 'REFUND_CREATED'
    INSTALLMENT_CREATED = 'INSTALLMENT_CREATED'
    SPLIT_CREATED = 'SPLIT_CREATED'
    ORDER_ON_HOLD = 'ORDER_ON_HOLD'
    ORDER_PAID = 'ORDER_PAID'
    ORDER_EXPIRED = 'ORDER_EXPIRED'
    PAYMENT_DECLINED = 'PAYMENT_DECLINED'
    PAYMENT_ACTION_REQUIRED = 'PAYMENT_ACTION_REQUIRED'
    PAYMENT_APPROVED = 'PAYMENT_APPROVED'
    PAYMENT_CAPTURED = 'PAYMENT_CAPTURED'
    CAPTURE_DECLINED = 'CAPTURE_DECLINED'
    PAYMENT_CANCELLED = 'PAYMENT_CANCELLED'
    CANCEL_DECLINED = 'CANCEL_DECLINED'
    REFUND_APPROVED = 'REFUND_APPROVED'
    REFUND_DECLINED = 'REFUND_DECLINED'
    SPLIT_APPROVED = 'SPLIT_APPROVED'
    SPLIT_DECLINED = 'SPLIT_DECLINED'
    SPLIT_REFUND_APPROVED = 'SPLIT_REFUND_APPROVED'
    SPLIT_REFUND_DECLINED = 'SPLIT_REFUND_DECLINED'
    CHECK_APPROVED = 'CHECK_APPROVED'
    CHECK_DECLINED = 'CHECK_DECLINED'
    OTP_SENT = 'OTP_SENT'
    SEND_OTP_DECLINED = 'SEND_OTP_DECLINED'
    OTP_CONFIRMED = 'OTP_CONFIRMED'
    CONFIRM_OTP_DECLINED = 'CONFIRM_OTP_DECLINED'
    INSTALLMENT_ACTION_REQUIRED = 'INSTALLMENT_ACTION_REQUIRED'
    INSTALLMENT_ISSUED = 'INSTALLMENT_ISSUED'
    INSTALLMENT_REJECTED = 'INSTALLMENT_REJECTED'
    INSTALLMENT_DECLINED = 'INSTALLMENT_DECLINED'


class CustomerStatus(str, enum.Enum):
    PENDING = 'PENDING'
    READY = 'READY'


class AccountStatus(str, enum.Enum):
    PENDING = 'PENDING'
    ACCEPTED = 'ACCEPTED'
    BLOCKED = 'BLOCKED'


class TaxType(enum.IntEnum):
    WITHOUT = 0
    WITH = 100


@dataclasses.dataclass
class _Model:
    client: typing.Any = dataclasses.field(
        init=True,
        repr=False,
    )


@dataclasses.dataclass
class Payer:
    type: PayerType
    pan_masked: typing.Optional[str]
    expiry_date: typing.Optional[str]
    holder: typing.Optional[str]
    payment_system: typing.Optional[str]
    emitter: typing.Optional[str]
    email: typing.Optional[str]
    phone: typing.Optional[str]
    customer_id: typing.Optional[str]
    card_id: typing.Optional[str]


@dataclasses.dataclass
class ErrorModel:
    code: str
    message: str


@dataclasses.dataclass
class Acquirer:
    name: str
    reference: typing.Optional[str]


@dataclasses.dataclass
class Action:
    url: str


@dataclasses.dataclass
class Order(_Model):
    id: str
    shop_id: str
    status: OrderStatus
    created_at: datetime.datetime
    amount: Money
    capture_method: CaptureMethod
    external_id: typing.Optional[str]
    description: typing.Optional[str]
    extra_info: typing.Optional[dict]
    mcc: typing.Optional[str]
    acquirer: typing.Optional[str]
    customer_id: typing.Optional[str]
    card_id: typing.Optional[str]
    attempts: typing.Optional[int]
    checkout_url: str
    payments: typing.Optional[list['Payment']]

    def cancel(self, reason: typing.Optional[str] = None) -> 'Payment':
        return self.client.cancel_order(self.id, reason=reason)

    def capture(
        self,
        amount: typing.Optional[Money] = None,
        reason: typing.Optional[str] = None,
    ) -> 'Payment':
        if amount is None:
            amount = self.amount
        if amount.minors > self.amount.minors:
            raise RuntimeError(
                f'cannot capture more than {self.amount}',
            )
        return self.client.capture_order(amount, reason=reason)

    def update(self, amount: Money) -> None:
        self.client.order_update(self.id, amount)
        self.amount = amount

    def events(self) -> list['Event']:
        return self.client.order_events(self.id)


# TODO: Change amount type to Money
@dataclasses.dataclass
class Payment:
    id: str
    order_id: str
    status: PaymentStatus
    created_at: datetime.datetime
    approved_amount: int
    captured_amount: int
    refunded_amount: int
    processing_fee: float
    payer: typing.Optional[Payer]
    error: typing.Optional[ErrorModel]
    acquirer: typing.Optional[Acquirer]
    action: typing.Optional[Action]


@dataclasses.dataclass
class RefundRule:
    account_id: str
    amount: Money


@dataclasses.dataclass
class Refund:
    id: str
    payment_id: str
    order_id: str
    status: RefundStatus
    created_at: typing.Optional[datetime.datetime]
    error: typing.Optional[ErrorModel]
    acquirer: typing.Optional[Acquirer]


@dataclasses.dataclass
class Event(ErrorModel):
    id: str
    name: EventName
    created_at: datetime.datetime
    order_id: str
    payment_id: typing.Optional[str]
    refund_id: typing.Optional[str]
    md: typing.Optional[str]
    pa_req: typing.Optional[str]
    acs_url: typing.Optional[str]
    term_url: typing.Optional[str]
    action_url: typing.Optional[str]


@dataclasses.dataclass
class AccountResource:
    id: str
    iban: str
    is_default: bool


@dataclasses.dataclass
class Account:
    id: str
    shop_id: str
    customer_id: typing.Optional[str]
    status: AccountStatus
    name: str
    amount: Money
    resources: list[AccountResource]
    created_at: datetime.datetime
    external_id: typing.Optional[str]


# TODO: Change ints to Money if necessary
@dataclasses.dataclass
class CheckPosition:
    name: str
    amount: Money
    count: int
    section: int
    tax_percent: int
    tax_type: TaxType = TaxType.WITHOUT
    tax_amount: int = 0
    unit_code: int = 0


@dataclasses.dataclass
class Customer:
    id: str
    created_at: datetime.datetime
    status: CustomerStatus
    external_id: typing.Optional[str]
    email: typing.Optional[str]
    phone: typing.Optional[str]
    accounts: typing.Optional[list[Account]]
    checkout_url: str
    access_token: str
