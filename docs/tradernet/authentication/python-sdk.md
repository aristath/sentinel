# Tradernet Python SDK

### Author: Anton Kudelin.

MIT license

### Connection arguments

### Sample connections:

#### Configuration in arguments:

```json
        Learn more        PyPI tradernet-sdk.



            An authorised user may receive the keys on page            «API key»



            The password is transferred to the Tradernet POST server by a request.




from tradernet import TraderNetAPI

api = TraderNetAPI('public_key', 'private_key', 'login', 'passwd')
api.user_info()
```

#### From the configuration file:

```json
from tradernet import Trading, TraderNetCore

config = TraderNetCore.from_config('tradernet.ini')

order = Trading.from_instance(config)
result = order.buy('AAPL.US', quantity=1, price=0.4, use_margin=False)
print(result)
```

#### Sample configuration file:

```json
[auth]
public   = public_key
private  = private_key
login    = login
password = passwd
```

#### Sample option operation

```json
from tradernet import TraderNetOption

option = TraderNetOption('+FRHC.16SEP2022.C55')
print(option)
```

```json
from tradernet import DasOption

option = DasOption('+FRHC^C7F45.US')
print(option)
```

#### Sample connection to WebSocket:

```json
from tradernet import TraderNetWSAPI, TraderNetCore

config = TraderNetCore.from_config('tradernet.ini')

async def main() -> None:
    async with TraderNetWSAPI(config) as wsapi:  # type: TraderNetWSAPI
        async for quote in wsapi.quotes('FRHC.US'):
            print(quote)

if __name__ == '__main__':
    asyncio.run(main())
```

#### Receiving formatted data:

```json
from tradernet import TraderNetSymbol, TraderNetCore

config = TraderNetCore.from_config('tradernet.ini')

symbol = TraderNetSymbol('AAPL.US', TraderNetAPI.from_instance(config))
symbol.get_data()

print(symbol.market_data.head().to_markdown())
```

#### Compatible with the legacy PublicApiClient library for Python

Tradernet Python SDK enables using the legacy Tradernet library

```json
from tradernet import NtApi

pub_ = '[public Api key]'
sec_ = '[secret Api key]'

res = NtApi(pub_, sec_, NtApi.V2)
print(res.sendRequest('getPositionJson'))
```

### Pages with examples (section Python):
