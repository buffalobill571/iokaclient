iokaclient
=============

.. start-inclusion-marker-do-not-remove

.. image:: https://github.com/buffalobill571/iokaclient/workflows/CI/badge.svg?event=push
   :alt: Build Status
   :target: https://github.com/buffalobill571/iokaclient/actions?query=event%3Apush+branch%3Amaster+workflow%3ACI


Ioka python client, supports both synchronous and asynchronous operations.

Installation
------------

Since `iokaclient` not released at PyPi, install `httpx` first:

.. code:: bash

   pip install httpx

then:

.. code:: bash

   pip install -i https://test.pypi.org/simple/ iokaclient


Reasoning
---------

Unlike other available clients, this one:

- Supports modern Python versions
- Does not use global variables for set up `<https://stackoverflow.com/questions/19158339/why-are-global-variables-evil>`
- Supports both synchronous and asynchronous ways of doing operations
- Uses connection pooling
- Stricly linted
- Supports ORM like interactivity for Order instance
- Strongly typed and highly predictable according to API specification
- Will be tested with 100% coverage... soon :)
- Uses only Python standart lib, except HTTP client


Configuration
-------------

Create client, using api key and endpoint url:

.. code:: python

   import ioka

   client = ioka.Ioka(api_key=..., base_url=...)

Usage
-----

First, create order:

.. code:: python

   order = client.create_order(
      ioka.KZT(500),
      capture_method=ioka.CaptureMethod.AUTO,
      ...,  # for all available options, see the code
   )
   # OR async version (options omitted, but signature is similar)
   # in the next examples, async version will not be presented, but they are still available with `a_` prefix
   order = await client.a_create_order(ioka.KZT(500))

Returned order instance has all available attributes, also has instance scoped operations, for example:

.. code:: python

   cancelled_payment = order.cancel()
   captured_payment = order.capture()
   payments = order.get_payments()
   refunds = order.get_refunds()

   order.amount = ioka.KZT(1000)
   order.update()  # amount will be updated, according to API spec

If you are not fan of ORM style, still can use client methods:

.. code:: python

   cancelled_payment = client.cancel_order(order.id, reason='whatever reason')
   captured_payment = client.captured_payment(order.id, reason='another reason')
   payments = client.get_payments(order.id, page=2, limit=3)
   refunds = client.get_refunds(order.id)

   updated_order = client.update_order(order.id, ioka.KZT(1000))

Also available operations with customers and their accounts:

.. code:: python

   customers = client.get_customers(status=ioka.CustomerStatus.READY)
   accounts = client.get_accounts()

Error handling
--------------

Base exception is `ioka.Error`, see the exception hierarchy for better experience:

- Error
   - TimeoutError
   - StatusError
      - ValidationError
      - UnauthenticatedError
      - UnauthorizedError
      - NotFoundError
      - ConflictError

`StatusError` and its descendants have `code`, `status_code` and `message` attributes, sample representation:

.. code:: python

   ConflictError(status_code=<httpx.codes.CONFLICT: 409>, message='Заказ не оплачен. Возврат невозможен', code='OrderUnpaid')

TODO
----

- Make 100% test coverage
- Split integration tests from unit tests, make sure test credentials are hidden
- Discuss about specification mismatch
- Grep lib for TODO's
- Make stable release to production PyPi
- Configure releasing through github actions
