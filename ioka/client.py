import datetime
import functools
import os
import typing

import httpx

from . import exceptions, models


_JsonTypes = typing.Union[dict, list]


def _parse_datetime(d_str: str) -> datetime.datetime:
    return datetime.datetime.strptime(d_str, '%Y-%m-%dT%H:%M:%S.%f')


def _get_money(amount: int, currency: str):
    money_cls: models.Money = getattr(models, currency)

    if money_cls is None:
        raise RuntimeError(f'Unrecognized currency {currency!r}')

    return money_cls.from_minor(amount)


def _drop_out_nones(entry: dict):
    return {k: v for k, v in entry.items() if v is not None}


class _Auth(httpx.Auth):
    def __init__(self, api_key) -> None:
        self._api_key = api_key

    def auth_flow(self, request):
        request.headers['api-key'] = self._api_key
        yield request


class _Client:
    version = 'v2'

    def __init__(
        self,
        api_key: str,
        base_url: str = 'https://stage-api.ioka.kz',
        timeout: typing.Optional[float] = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout

    @functools.cached_property
    def _client(self):
        return httpx.Client(
            auth=_Auth(self._api_key),
            base_url=os.path.join(self._base_url, self.version),
            timeout=self._timeout,
        )

    @functools.cached_property
    def _a_client(self):
        return httpx.AsyncClient(
            auth=_Auth(self._api_key),
            base_url=os.path.join(self._base_url, self.version),
            timeout=self._timeout,
        )

    def _process(self, response: httpx.Response) -> _JsonTypes:
        response_body = response.json()

        if httpx.codes.is_success(response.status_code):
            return response_body
        elif response.status_code == httpx.codes.BAD_REQUEST:
            raise exceptions.ValidationError(
                message=response_body['message'],
                code=response_body['code'],
            )
        elif response.status_code == httpx.codes.UNAUTHORIZED:
            raise exceptions.UnauthenticatedError(
                message=response_body['message'],
                code=response_body['code'],
            )
        elif response.status_code == httpx.codes.FORBIDDEN:
            raise exceptions.UnauthorizedError(
                message=response_body['message'],
                code=response_body['code'],
            )
        elif response.status_code == httpx.codes.NOT_FOUND:
            raise exceptions.NotFoundError(
                message=response_body['message'],
                code=response_body['code'],
            )
        elif response.status_code == httpx.codes.CONFLICT:
            raise exceptions.ConflictError(
                message=response_body['message'],
                code=response_body['code'],
            )
        else:
            raise exceptions.StatusError(
                status_code=response.status_code,
                message=response.text,
                code='Unknown',
            )

    def _request(self, method: str, url: str, **kwargs) -> _JsonTypes:
        try:
            return self._process(
                self._client.request(
                    method=method,
                    url=url,
                    **kwargs,
                ),
            )
        except httpx.TimeoutException as e:
            raise exceptions.TimeoutError from e
        except httpx.HTTPError as e:
            raise exceptions.Error(str(e)) from e

    async def _a_request(self, method: str, url: str, **kwargs) -> _JsonTypes:
        try:
            return self._process(
                await self._a_client.request(
                    method=method,
                    url=url,
                    **kwargs,
                ),
            )
        except httpx.TimeoutException as e:
            raise exceptions.TimeoutError from e
        except httpx.HTTPError as e:
            raise exceptions.Error(str(e)) from e


class Ioka(_Client):
    """Ioka client.

    Supports both synchronous and asynchronous operations. Async
    operations starts with 'a' prefix. """

    def _dict_to_account(self, account: dict) -> models.Account:
        resources = None

        if 'resources' in account and account['resources'] is not None:
            resources = [
                models.AccountResource(
                    id=resource['id'],
                    iban=resource.get('iban'),
                    is_default=resource.get('is_default'),
                )
                for resource in account['resources']
            ]

        return models.Account(
            id=account['id'],
            shop_id=account['shop_id'],
            customer_id=account.get('customer_id'),
            status=models.AccountStatus(account['status']),
            name=account.get('name'),
            # TODO: Discuss! Mismatch with the specification
            amount=_get_money(
                account['amount'],
                account.get('currency', 'KZT'),
            ),
            resources=resources,
            created_at=_parse_datetime(account['created_at']),
            external_id=account.get('external_id'),
        )

    def _dict_to_customer(self, customer: dict) -> models.Customer:
        accounts = None

        if 'accounts' in customer and customer['accounts'] is not None:
            accounts = [
                self._dict_to_account(account)
                for account in customer['accounts']
            ]

        return models.Customer(
            id=customer['id'],
            created_at=_parse_datetime(customer['created_at']),
            status=models.CustomerStatus(customer['status']),
            # TODO: Discuss, mismatch with the specification
            external_id=customer.get('external_id'),
            email=customer.get('email'),
            phone=customer.get('phone'),
            accounts=accounts,
            checkout_url=customer['checkout_url'],
            access_token=customer['access_token'],
        )

    def _dict_to_payment(self, payment: dict) -> models.Payment:
        payer = None
        if 'payer' in payment and payment['payer'] is not None:
            payer_ = payment['payer']
            payer = models.Payer(
                type=models.PayerType(payer_['type']),
                pan_masked=payer_['pan_masked'],
                expiry_date=payer_['expiry_date'],
                holder=payer_['holder'],
                payment_system=payer_['payment_system'],
                emitter=payer_['emitter'],
                email=payer_['email'],
                phone=payer_['phone'],
                customer_id=payer_['customer_id'],
                card_id=payer_['card_id'],
            )
        error = None
        if 'error' in payment and payment['error'] is not None:
            error = models.ErrorModel(
                code=payment['error']['code'],
                message=payment['error']['message'],
            )

        acquirer = None
        if 'acquirer' in payment and payment['acquirer'] is not None:
            acquirer = models.Acquirer(
                name=payment['acquirer']['name'],
                reference=payment['acquirer']['reference'],
            )
        action = None
        if 'action' in payment and payment['action'] is not None:
            action = models.Action(
                url=payment['action']['url'],
            )

        return models.Payment(
            id=payment['id'],
            shop_id=payment['shop_id'],
            order_id=payment['order_id'],
            status=models.PaymentStatus(payment['status']),
            created_at=_parse_datetime(payment['created_at']),
            approved_amount=payment['approved_amount'],
            captured_amount=payment['captured_amount'],
            refunded_amount=payment['refunded_amount'],
            processing_fee=payment['processing_fee'],
            payer=payer,
            error=error,
            acquirer=acquirer,
            action=action,
        )

    def _dict_to_order(self, order: dict) -> models.Order:
        payments = None

        if 'payments' in order and order['payments'] is not None:
            payments = [
                self._dict_to_order(payment)
                for payment in order['payments']
            ]

        return models.Order(
            client=self,
            id=order['id'],
            shop_id=order['shop_id'],
            status=models.OrderStatus(order['status']),
            created_at=_parse_datetime(order['created_at']),
            amount=_get_money(order['amount'], order['currency']),
            capture_method=models.CaptureMethod(order['capture_method']),
            external_id=order['external_id'],
            description=order['description'],
            extra_info=order['extra_info'],
            mcc=order['mcc'],
            acquirer=order['acquirer'],
            customer_id=order['customer_id'],
            card_id=order['card_id'],
            attempts=order['attempts'],
            checkout_url=order['checkout_url'],
            payments=payments,
        )

    def _dict_to_refund(self, refund: dict) -> models.Refund:
        error = None
        if 'error' in refund and refund['error'] is not None:
            error = models.ErrorModel(
                code=refund['error']['code'],
                message=refund['error']['message'],
            )
        acquirer = None
        if 'acquirer' in refund and refund['acquirer'] is not None:
            acquirer = models.Acquirer(
                name=refund['acquirer']['name'],
                reference=refund['acquirer']['reference'],
            )
        return models.Refund(
            id=refund['id'],
            payment_id=refund['payment_id'],
            order_id=refund['order_id'],
            status=models.RefundStatus(refund['status']),
            created_at=_parse_datetime(refund['created_at']),
            error=error,
            acquirer=acquirer,
        )

    def _prepare_refund_create_body(
        self,
        amount: models.Money,
        reason: typing.Optional[str] = None,
        rules: typing.Optional[list[models.RefundRule]] = None,
        positions: typing.Optional[list[models.CheckPosition]] = None,
    ) -> dict:
        if rules is not None:
            rules = [
                {
                    'account_id': rule.account_id,
                    'amount': rule.amount.minors,
                } for rule in rules
            ]
        if positions is not None:
            positions = [
                _drop_out_nones({
                    'name': position.name,
                    'amount': position.amount.minors,
                    'section': position.section,
                    'tax_percent': position.tax_percent,
                    'tax_type': (
                        position.tax_type.value
                        if position.tax_type is not None else None
                    ),
                    'tax_amount': position.tax_amount,
                    'unit_code': position.unit_code,
                }) for position in positions
            ]
        return _drop_out_nones({
            'amount': amount.minors,
            'reason': reason,
            'rules': rules,
        })

    def _prepare_order_create_body(
        self,
        amount: models.Money,
        capture_method: models.CaptureMethod = models.CaptureMethod.AUTO,
        external_id: typing.Optional[str] = None,
        description: typing.Optional[str] = None,
        mcc: typing.Optional[str] = None,
        extra_info: typing.Optional[dict] = None,
        attempts: typing.Optional[int] = None,
        due_date: typing.Optional[datetime.datetime] = None,
        customer_id: typing.Optional[str] = None,
        card_id: typing.Optional[str] = None,
        back_url: typing.Optional[str] = None,
        success_url: typing.Optional[str] = None,
        failure_url: typing.Optional[str] = None,
        template: typing.Optional[str] = None,
    ) -> dict:
        return _drop_out_nones({
            'amount': amount.minors,
            'capture_method': capture_method.value,
            'external_id': external_id,
            'description': description,
            'mcc': mcc,
            'extra_info': extra_info,
            'attempts': attempts,
            'due_date': due_date.isoformat() if due_date is not None else None,
            'customer_id': customer_id,
            'card_id': card_id,
            'back_url': back_url,
            'success_url': success_url,
            'failure_url': failure_url,
            'template': template,
        })

    def _prepare_pagination_filter_params(
        self,
        page: int = 1,
        limit: int = 10,
        from_dt: typing.Optional[datetime.datetime] = None,
        to_dt: typing.Optional[datetime.datetime] = None,
        date_category: typing.Optional[models.DateCategory] = None,
        customer_id: typing.Optional[str] = None,
        external_id: typing.Optional[str] = None,
        status: typing.Optional[models.enum.Enum] = None,
        order_id: typing.Optional[str] = None,
        payment_id: typing.Optional[str] = None,
        pan_first6: typing.Optional[str] = None,
        pan_last4: typing.Optional[str] = None,
        payer_email: typing.Optional[str] = None,
        payer_phone: typing.Optional[str] = None,
        payment_status: typing.Optional[models.PaymentStatus] = None,
        payment_system: typing.Optional[str] = None,
        amount_category: typing.Optional[models.AmountCategory] = None,
        fixed_amount: typing.Optional[models.Money] = None,
        min_amount: typing.Optional[models.Money] = None,
        max_amount: typing.Optional[models.Money] = None,
    ):
        return _drop_out_nones({
            'page': page,
            'limit': limit,
            'from_dt': from_dt.isoformat() if from_dt is not None else None,
            'to_dt': to_dt.isoformat() if to_dt is not None else None,
            'date_category': (
                date_category.value if date_category is not None else None
            ),
            'customer_id': customer_id,
            'external_id': external_id,
            'status': status.value if status is not None else None,
            'order_id': order_id,
            'payment_id': payment_id,
            'pan_first6': pan_first6,
            'pan_last4': pan_last4,
            'payer_email': payer_email,
            'payer_phone': payer_phone,
            'payment_status': (
                payment_status.value if payment_status is not None else None
            ),
            'payment_system': payment_system,
            'amount_category': (
                amount_category.value if amount_category is not None else None
            ),
            'fixed_amount': (
                fixed_amount.minors if fixed_amount is not None else None
            ),
            'min_amount': (
                min_amount.minors if min_amount is not None else None
            ),
            'max_amount': (
                max_amount.minors if max_amount is not None else None
            ),
        })

    def create_order(
        self,
        amount: models.Money,
        capture_method: models.CaptureMethod = models.CaptureMethod.AUTO,
        external_id: typing.Optional[str] = None,
        description: typing.Optional[str] = None,
        mcc: typing.Optional[str] = None,
        extra_info: typing.Optional[dict] = None,
        attempts: typing.Optional[int] = None,
        due_date: typing.Optional[datetime.datetime] = None,
        customer_id: typing.Optional[str] = None,
        card_id: typing.Optional[str] = None,
        back_url: typing.Optional[str] = None,
        success_url: typing.Optional[str] = None,
        failure_url: typing.Optional[str] = None,
        template: typing.Optional[str] = None,
    ) -> (models.Order, str):
        response = self._request(
            'post',
            '/orders',
            json=self._prepare_order_create_body(
                amount=amount,
                capture_method=capture_method,
                external_id=external_id,
                description=description,
                mcc=mcc,
                extra_info=extra_info,
                attempts=attempts,
                due_date=due_date,
                customer_id=customer_id,
                card_id=card_id,
                back_url=back_url,
                success_url=success_url,
                failure_url=failure_url,
                template=template,
            ),
        )

        return (
            self._dict_to_order(response['order']),
            response['order_access_token'],
        )

    async def a_create_order(
        self,
        amount: models.Money,
        capture_method: models.CaptureMethod = models.CaptureMethod.AUTO,
        external_id: typing.Optional[str] = None,
        description: typing.Optional[str] = None,
        mcc: typing.Optional[str] = None,
        extra_info: typing.Optional[dict] = None,
        attempts: typing.Optional[int] = None,
        due_date: typing.Optional[datetime.datetime] = None,
        customer_id: typing.Optional[str] = None,
        card_id: typing.Optional[str] = None,
        back_url: typing.Optional[str] = None,
        success_url: typing.Optional[str] = None,
        failure_url: typing.Optional[str] = None,
        template: typing.Optional[str] = None,
    ) -> (models.Order, str):
        response = await self._a_request(
            'post',
            '/orders',
            json=self._prepare_order_create_body(
                amount=amount,
                capture_method=capture_method,
                external_id=external_id,
                description=description,
                mcc=mcc,
                extra_info=extra_info,
                attempts=attempts,
                due_date=due_date,
                customer_id=customer_id,
                card_id=card_id,
                back_url=back_url,
                success_url=success_url,
                failure_url=failure_url,
                template=template,
            ),
        )

        return (
            self._dict_to_order(response['order']),
            response['order_access_token'],
        )

    def get_orders(
        self,
        page: int = 1,
        limit: int = 10,
        from_dt: typing.Optional[datetime.datetime] = None,
        to_dt: typing.Optional[datetime.datetime] = None,
        date_category: typing.Optional[models.DateCategory] = None,
    ):
        return [
            self._dict_to_order(order) for order in self._request(
                'get',
                '/orders',
                params=self._prepare_pagination_filter_params(
                    page=page,
                    limit=limit,
                    from_dt=from_dt,
                    to_dt=to_dt,
                    date_category=date_category,
                ),
            )
        ]

    async def a_get_orders(
        self,
        page: int = 1,
        limit: int = 10,
        from_dt: typing.Optional[datetime.datetime] = None,
        to_dt: typing.Optional[datetime.datetime] = None,
        date_category: typing.Optional[models.DateCategory] = None,
    ):
        return [
            self._dict_to_order(order) for order in await self._a_request(
                'get',
                '/orders',
                params=self._prepare_pagination_filter_params(
                    page=page,
                    limit=limit,
                    from_dt=from_dt,
                    to_dt=to_dt,
                    date_category=date_category,
                ),
            )
        ]

    def capture_order(
        self,
        order_id: str,
        amount: models.Money,
        reason: typing.Optional[str] = None,
    ) -> models.Payment:
        return self._dict_to_order(
            self._request(
                'post',
                f'/orders/{order_id}/capture',
                json=_drop_out_nones({
                    'amount': amount.minors,
                    'reason': reason,
                }),
            ),
        )

    async def a_capture_order(
        self,
        order_id: str,
        amount: models.Money,
        reason: typing.Optional[str] = None,
    ) -> models.Payment:
        return self._dict_to_order(
            await self._a_request(
                'post',
                f'/orders/{order_id}/capture',
                json=_drop_out_nones({
                    'amount': amount.minors,
                    'reason': reason,
                }),
            ),
        )

    def cancel_order(
        self,
        order_id: str,
        reason: typing.Optional[str] = None,
    ) -> models.Payment:
        return self._dict_to_order(
            self._request(
                'post',
                f'/orders/{order_id}/cancel',
                json=_drop_out_nones({
                    'reason': reason,
                }),
            ),
        )

    async def a_cancel_order(
        self,
        order_id: str,
        reason: typing.Optional[str] = None,
    ) -> models.Payment:
        return self._dict_to_order(
            await self._a_request(
                'post',
                f'/orders/{order_id}/cancel',
                json=_drop_out_nones({
                    'reason': reason,
                }),
            ),
        )

    def update_order(
        self,
        order_id: str,
        amount: models.Money,
    ) -> models.Order:
        return self._dict_to_order(
            self._request(
                'patch',
                f'/orders/{order_id}',
                json={
                    'amount': amount.minors,
                },
            ),
        )

    async def a_update_order(
        self,
        order_id: str,
        amount: models.Money,
    ) -> models.Order:
        return self._dict_to_order(
            await self._a_request(
                'patch',
                f'/orders/{order_id}',
                json={
                    'amount': amount.minors,
                },
            ),
        )

    def get_refunds(
        self,
        order_id: str,
    ) -> list[models.Refund]:
        return [
            self._dict_to_refund(refund)
            for refund in self._request(
                'get',
                f'/orders/{order_id}/refunds',
            )
        ]

    async def a_get_refunds(
        self,
        order_id: str,
    ) -> list[models.Refund]:
        return [
            self._dict_to_refund(refund)
            for refund in await self._a_request(
                'get',
                f'/orders/{order_id}/refunds',
            )
        ]

    def create_refund(
        self,
        order_id: str,
        amount: models.Money,
        reason: typing.Optional[str] = None,
        rules: typing.Optional[list[models.RefundRule]] = None,
        positions: typing.Optional[list[models.CheckPosition]] = None,
    ) -> models.Refund:
        return self._dict_to_refund(
            self._request(
                'post',
                f'/orders/{order_id}/refunds',
                json=self._prepare_refund_create_body(
                    amount=amount,
                    reason=reason,
                    rules=rules,
                    positions=positions,
                ),
            ),
        )

    async def a_create_refund(
        self,
        order_id: str,
        amount: models.Money,
        reason: typing.Optional[str] = None,
        rules: typing.Optional[list[models.RefundRule]] = None,
        positions: typing.Optional[list[models.CheckPosition]] = None,
    ) -> models.Refund:
        return self._dict_to_refund(
            await self._a_request(
                'post',
                f'/orders/{order_id}/refunds',
                json=self._prepare_refund_create_body(
                    amount=amount,
                    reason=reason,
                    rules=rules,
                    positions=positions,
                ),
            ),
        )

    def get_payments(
        self,
        order_id: str,
        page: int = 1,
        limit: int = 10,
        from_dt: typing.Optional[datetime.datetime] = None,
        to_dt: typing.Optional[datetime.datetime] = None,
        date_category: typing.Optional[models.DateCategory] = None,
        external_id: typing.Optional[str] = None,
        payment_id: typing.Optional[str] = None,
        pan_first6: typing.Optional[str] = None,
        pan_last4: typing.Optional[str] = None,
        payer_email: typing.Optional[str] = None,
        payer_phone: typing.Optional[str] = None,
        customer_id: typing.Optional[str] = None,
        payment_status: typing.Optional[models.PaymentStatus] = None,
        payment_system: typing.Optional[str] = None,
    ):
        return [
            self._dict_to_payment(payment)
            for payment in self._request(
                'get',
                f'/orders/{order_id}/payments',
                params=self._prepare_pagination_filter_params(
                    page=page,
                    limit=limit,
                    from_dt=from_dt,
                    to_dt=to_dt,
                    date_category=date_category,
                    external_id=external_id,
                    payment_id=payment_id,
                    pan_first6=pan_first6,
                    pan_last4=pan_last4,
                    payer_email=payer_email,
                    payer_phone=payer_phone,
                    customer_id=customer_id,
                    payment_status=payment_status,
                    payment_system=payment_system,
                ),
            )
        ]

    async def a_get_payments(
        self,
        order_id: str,
        page: int = 1,
        limit: int = 10,
        from_dt: typing.Optional[datetime.datetime] = None,
        to_dt: typing.Optional[datetime.datetime] = None,
        date_category: typing.Optional[models.DateCategory] = None,
        external_id: typing.Optional[str] = None,
        payment_id: typing.Optional[str] = None,
        pan_first6: typing.Optional[str] = None,
        pan_last4: typing.Optional[str] = None,
        payer_email: typing.Optional[str] = None,
        payer_phone: typing.Optional[str] = None,
        customer_id: typing.Optional[str] = None,
        payment_status: typing.Optional[models.PaymentStatus] = None,
        payment_system: typing.Optional[str] = None,
    ):
        return [
            self._dict_to_payment(payment)
            for payment in await self._a_request(
                'get',
                f'/orders/{order_id}/payments',
                params=self._prepare_pagination_filter_params(
                    page=page,
                    limit=limit,
                    from_dt=from_dt,
                    to_dt=to_dt,
                    date_category=date_category,
                    external_id=external_id,
                    payment_id=payment_id,
                    pan_first6=pan_first6,
                    pan_last4=pan_last4,
                    payer_email=payer_email,
                    payer_phone=payer_phone,
                    customer_id=customer_id,
                    payment_status=payment_status,
                    payment_system=payment_system,
                ),
            )
        ]

    def get_customers(
        self,
        limit: int = 10,
        page: int = 1,
        from_dt: typing.Optional[datetime.datetime] = None,
        to_dt: typing.Optional[datetime.datetime] = None,
        date_category: typing.Optional[models.DateCategory] = None,
        customer_id: typing.Optional[str] = None,
        external_id: typing.Optional[str] = None,
        status: typing.Optional[models.CustomerStatus] = None,
    ) -> list[models.Customer]:
        return [
            self._dict_to_customer(customer)
            for customer in self._request(
                'get',
                '/customers',
                params=self._prepare_pagination_filter_params(
                    page=page,
                    limit=limit,
                    from_dt=from_dt,
                    to_dt=to_dt,
                    date_category=date_category,
                    customer_id=customer_id,
                    external_id=external_id,
                    status=status,
                ),
            )
        ]

    async def a_get_customers(
        self,
        limit: int = 10,
        page: int = 1,
        from_dt: typing.Optional[datetime.datetime] = None,
        to_dt: typing.Optional[datetime.datetime] = None,
        date_category: typing.Optional[models.DateCategory] = None,
        customer_id: typing.Optional[str] = None,
        external_id: typing.Optional[str] = None,
        status: typing.Optional[models.CustomerStatus] = None,
    ) -> list[models.Customer]:
        return [
            self._dict_to_customer(customer)
            for customer in self._a_request(
                'get',
                '/customers',
                params=self._prepare_pagination_filter_params(
                    page=page,
                    limit=limit,
                    from_dt=from_dt,
                    to_dt=to_dt,
                    date_category=date_category,
                    customer_id=customer_id,
                    external_id=external_id,
                    status=status,
                ),
            )
        ]

    def get_accounts(self) -> list[models.Account]:
        return [
            self._dict_to_account(account)
            for account in self._request('get', '/accounts')
        ]

    async def a_get_accounts(self) -> list[models.Account]:
        return [
            self._dict_to_account(account)
            for account in await self._request('get', '/accounts')
        ]
