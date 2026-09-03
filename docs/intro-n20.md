Cumulocity's Notification 2.0 service pushes real-time notifications about
database changes (measurements, events, alarms, managed objects and
operations) over a websocket-based protocol, instead of having clients poll
for changes.

The Cumulocity Python SDK provides the
[Subscription][pyc8y.model.Subscription] class to manage what a subscriber
should receive, and the [Listener][pyc8y.notification2.Listener] class to
consume the notification stream without dealing with the underlying
protocol (tokens, websocket handling, acknowledgements, reconnects).

Each [Message][pyc8y.notification2.Message] wraps a single notification;
`message.json` gives you the parsed payload, `message.ack()` acknowledges
it.

``` python
from pyc8y.model import Subscription
from pyc8y.notification2 import Listener

# subscribe to all measurements of a device
subscription = await Subscription(
    c8y,
    name='myAppSubscription',
    context=Subscription.Context.MANAGED_OBJECT,
    source_id=device_id,
    api_filter=[Subscription.ApiFilter.MEASUREMENTS],
).create()

async def handle(message):
    print(f"Received: {message.json}")
    await message.ack()

listener = Listener(c8y, subscription_name=subscription.name)
listener.start(handle)

# ... do other things, then eventually ...
listener.stop()
await listener.wait()
```

If you would rather consume notifications like any other async
iterable instead of via callback, use
[QueueListener][pyc8y.notification2.QueueListener], which pushes messages
into an `asyncio.Queue` and acknowledges them automatically:

``` python
import asyncio
from pyc8y.notification2 import QueueListener

queue = asyncio.Queue()
listener = QueueListener(c8y, subscription_name=subscription.name, queue=queue)
listener.start()

message = await queue.get()
print(message.json)

listener.stop()
await listener.wait()
```