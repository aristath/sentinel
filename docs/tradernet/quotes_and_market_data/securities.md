# Directory of securities

The service enbles receiving information on securities from the server

### Description of server request parameters and a sample response:

#### Request:

```json
{
    "cmd" (string): "getAllSecurities",
    "params" (array): {
        "take" (int): 10,
        "skip" (int): 0
    }
}
```

#### Request parameters:

**Request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|

|---|---|---|---|
| take |   |   | Number of securities information on which is expected to be obtained
| skip |   |   |
| sort |   |   | Parameter used for sorting
| field | sort | string | Field to be used for sorting
| dir | sort | string | Sorting direction
| filter |   |   | Filtering
| filters | filter |   |
| field | filters | string | Field to be used for filtering
| operator | filters | string | Filtering operator
| value | filters | string | Value

#### Description of fields that can be filtered and sorted

**Description of fields that can be filtered and sorted:**

| Field name (field parameter) | Type | Description | Possible values
|---|---|---|---|
| ticker | string | Ticker in TS |
| instr_type | string | Instrument type. |
| instr_kind | string | Instrument sub-type |
| instr_kind_с | integer | Instrument subtype code |
| code_sec | string | Day trading code |
| code_rep | string | Night trading code |
| code_nm | string | Instrument ticker on the exchange |
| name | string | Name (for sorting only) |
| reg_nb | string | Registration number |
| issue_nb | string | Issue number |
| face_curr_c | string | Currency |
| mkt_id | integer | Market ID |
| mkt_name | string | Market code |
| mkt_short_code | string | Market short code |
| fv | numeric | Bond body value |
| step_price | numeric | Price increment |
| x_short | boolean | Available in short |

#### Description of filtering parameters:

**Description of filtering parameters::**

| Filtering operator (operator parameter) | Description
|---|---|---|---|
| eq | equal (default)
| neq | is not equal
| eqormore | Is greater than or equal to
| eqorless | Is less than or equal to
| isempty | For empty data
| contains | pattern matching anywhere in the string (similar to ILIKE%%)
| doesnotcontain | exclude from pattern matching anywhere in the string (similar to NOT ILIKE%%)
| startswith | string-start pattern matching (similar to ILIKE %)
| endswith | string-end pattern matching (similar to ILIKE% )
| in | listing multiple values separated by commas i enabled (similar to IN ( )

#### Response:

```json
{
        "securities":[{
            "ticker":"AAPL.US",
            "instr_type_c":1,
            "instr_type":"Ordinary stock",
            "instr_kind_c":1,
            "instr_kind":"Share",
            "instr_id":"40000001",
            "code_sec":"",
            "code_rep":"",
            "code_nm":"AAPL",
            "name":"Apple Inc.",
            "name_alt":"Apple Inc.",
            "reg_nb":"",
            "issue_nb":"US0378331005",
            "face_curr_c":"USD",
            "mkt_id":"30000000001",
            "mkt_name":"FIX",
            "lot_size_q":"1.00000000",
            "istrade":1,
            "maturity_d":null,
            "fv_calc":null,
            "issuesize":null,
            "fv":"100.00000000",
            "latname":"",
            "accint":null,
            "create_tmstmp":null,
            "update_tmstmp":"2020-02-11 13:09:37.120144",
            "to_delete":0,
            "mkt_short_code":"FIX",
            "x_short":1,
            "step_price":"0.01000000",
            "x_disc1":"0.01000000",
            "x_descr": "Apple Inc. is a recognized innovator and experimenter, dictating technological rules and fashion in computer design.",
            "quotes":"{
                "c": "AAPL.US",
                "n": 211,
                "fv": 100,
                "op": 222.77,
                "p5": 225.63,
                "pp": 220.7,
                "acd": 0,
                "baf": 0,
                "bap": 222.5,
                "bas": 500,
                "bbf": 0,
                "bbp": 222.5,
                "bbs": 200,
                "chg": 1.8,
                "cpn": 0,
                "cpp": 0,
                "dpb": 0,
                "dps": 0,
                "ltp": 222.5,
                "ltr": "FIX",
                "lts": 100,
                "ltt": "2019-09-18T19:54:03",
                "mrg": "M",
                "mtd": "",
                "ncd": "",
                "ncp": 0,
                "p22": 210.1,
                "pcp": 0.82,
                "rev": 199308,
                "vlt": 211458090.09,
                "vol": 949426,
                "yld": 0,
                "chg5": -2.13,
                "init": 1,
                "kind": 1,
                "name\": "Apple Inc.",
                "p110\": 186.7,
                "p220\": 223.45,
                "type": 1,
                "chg22": 5.11,
                "maxtp": 222.85,
                "mintp": 222.5,
                "name2": "",
                "x_lot": 1,
                "x_max": 231.7,
                "x_min": 142.12,
                "chg110": 18.28,
                "chg220": -1.17,
                "trades": 284,
                "x_curr": "USD",
                "x_dsc1": 25,
                "x_dsc2": 100,
                "x_dsc3": 100,
                "x_descr": "Apple Inc. is a recognized innovator and experimenter, dictating technological rules and fashion in computer design.",
                "x_short": 1,
                "base_ltr": "FIX",
                "issue_nb": "US0378331005",
                "min_step": 0.01,
                "otc_instr": "AAPL.US.OTC",
                "x_currVal": 64.15,
                "x_istrade": 1,
                "ClosePrice": 222.5,
                "step_price": 0.01,
                "scheme_calc": "T0",
                "yld_ytm_ask": 0,
                "yld_ytm_bid": 0,
                "base_currency": "",
                "x_agg_futures": "",
                "virt_base_instr": "",
                "x_dsc1_reception": "0=25.0000,1=25.0000,35=25.0000,37=25.0000,38=25.0000,43=25.0000",
                "x_short_reception": "0=1,1=1,35=1,37=1,38=1,43=1",
                "TradingSessionSubID": "",
                "TradingReferencePrice": 0
            }",
            "rate":10893,
            "id":113,
            "min_step":"0.01000000",
            "issuer_country_code":"US",
            "exchange_ticker":"AAPL",
            "maturity_code":null,
            "sector_code":"OTH",
            "currency_code":"840",
            "attributes":"{
                "CFICode": "EXXXXX",
                "min_step": "0.01000000",
                "limit_down": "0.00000000",
                "step_price": "0.01000000",
                "base_mkt_id": "FIX",
                "description": "Apple Inc. is a recognized innovator and experimenter, dictating technological rules and fashion in computer design.",
                "scheme_calc": "T0",
                "export_instrument_to_DIB": "yes"
            }",
            "codesub_nm":"NASDAQ",
            "bloomberg_id":"AAPL US Equity"
        }],
        "total":1
    }
```

**Description of response parameters::**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| securities |   | array |
| ticker | securities | string | Internal ticker in the TRADERNET system
| instr_type_c | securities | numeric | Instrument type
| instr_type | securities | string | Instrument type
| instr_kind_c | securities | numeric | Instrument sub-type
| instr_kind | securities | string | Instrument sub-type
| instr_id | securities | string | Instrument ID in the trading system
| code_sec | securities | string | Exchange trading mode" + "TQBD, WAPN, TQQQ, TQTD, RFND, FIXN, SETL, EQEU, SADM, SDBP, TQQD, EQBD, AETS, EQR2, EQMP, EQR3, PSRP, EQW2, PTTK, PRTK, EQQI, EQEO, EQRD, PSRD, PRTD, PTTD, EQLD, EQWD, EQR, PTKD, TQDE, PTOD, FUTN, TADM, LIQR, EQLP, RPMA, EQRP, TQTF, TQQI, EQDB, TQOB, TQIF, EQWP, TQOD, CETS, EQBR, PTKK, PTEQ, NADM, TRAN, TRAD, TQCB, TQBR, EQF, EQOB"
| code_rep | securities | string |
| code_nm | securities | string | Stock exchange ticker
| name | securities | string | Name
| name_alt | securities | string | Short Name
| reg_nb | securities | string | State registration number
| issue_nb | securities | string | ISIN
| face_curr_c | securities | string | Instrument currency
| mkt_id | securities | string | Market ID in the TRADERNET trading system
| mkt_name | securities | string | Market code in the TRADERNET trading system
| lot_size_q | securities | string | Lot size
| istrade | securities | numeric | Trading permitted in the TRADERNET trading system
| maturity_d | securities | string | Expiry date | fv_calc | securities | string |
| issuesize | securities | string | Volume of issued stock | fv | securities | string | nominal cost
| latname | securities | string | Name in English | accint | securities | string | Accumulated coupon interest (ACI)
| create_tmstmp | securities | string | Date of system entry | update_tmstmp | securities | string | Date of system update
| to_delete | securities | numeric | Security is removed from the system.
| mkt_short_code | securities | string | Short market code in the TRADERNET trading system
| x_short | securities | numeric | Short selling access
| step_price | securities | string | Price increment
| x_disc1 | securities | string | Discount
| x_descr | securities | string | Issuer description
| quotes | securities | JSON string | Quotes object
| c | quotes | string | Internal ticker in the TRADERNET system
| n | quotes | numeric | Serial quote number. Each ticker has its own number
| fv | quotes | string | nominal cost
| op | quotes | string | Opening price of the current trading session
| p5 | quotes | numeric | Price 5 days ago
| pp | quotes | numeric | Previous closing
| acd | quotes | numeric | Accumulated coupon interest (ACI)
| baf | quotes | numeric | Volume of the best ask
| bap | quotes | numeric | Best Ask
| bas | quotes | numeric | Best Ask size
| bbf | quotes | numeric | Best bid volume
| bbp | quotes | numeric | Best bid
| bbs | quotes | numeric | Best bid size
| chg | quotes | numeric | Change in the price of the last trade in points, relative to the closing price of the previous trading session
| cpn | quotes | numeric | Coupon, in the currency
| cpp | quotes | numeric | Coupon period (in days)
| dpb | quotes | numeric | Purchase margin
| dps | quotes | numeric | Short sale margin
| ltp | quotes | numeric | Last trade price
| ltr | quotes | string | Exchange of the latest trade
| lts | quotes | numeric | Last trade size
| ltt | quotes | string | Time of last trade
| mtd | quotes | string | Maturity date
| ncd | quotes | string | Next coupon date
| ncp | quotes | numeric | Latest coupon date
| p22 | quotes | numeric | Price 22 days ago
| pcp | quotes | numeric | Percentage change relative to the closing price of the previous trading session
| rev | quotes | numeric |
| vlt | quotes | numeric | Trading volume per day in currency
| vol | quotes | numeric | Trade volume per day, in pcs
| yld | quotes | numeric | Yield to maturity (for bonds)
| chg5 | quotes | numeric | Price change within a 5 day-period
| init | quotes | numeric |
| kind | quotes | numeric | Type of security (1 – Common, 2 – Preferred, 3 - Percent, 4 – Discount, 5 – Delivery, 6 – Rated, 7 - Interval)
| name | quotes | string | Name of security
| p110 | quotes | numeric |
| p220 | quotes | numeric | Price 220 days ago
| type | quotes | numeric | Type of security (1 - stocks, 2 - bonds, 3 - futures)
| chg22 | quotes | numeric | 22 day price change
| maxtp | quotes | numeric | Maximum trade price per day
| mintp | quotes | numeric | Minimum trade price per day
| name2 | quotes | string | Security name in Latin
| x_lot | quotes | numeric | Minimum lot size
| x_max | quotes | numeric | Maximum (for the period)
| x_min | quotes | numeric | Minimum (for the period)
| chg110 | quotes | numeric | Price change within a 110 day period
| chg220 | quotes | numeric |
| init | quotes | numeric | Price change within a 220 day-period
| trades | quotes | numeric | Number of trades
| x_curr | quotes | string | Currency
| x_dsc1 | quotes | numeric | Discount
| x_dsc2 | quotes | numeric | not used
| x_dsc3 | quotes | numeric | not used
| x_descr | quotes | string | Description
| x_short | quotes | numeric | Can a security be shorted?
| base_ltr | quotes | numeric | Base instrument market code
| issue_nb | quotes | numeric | ISIN
| min_step | quotes | numeric | Minimum price increment
| otc_instr | quotes | numeric | Instrument ticker on the OTC market
| x_currVal | quotes | numeric | Exchange rate to RUB
| x_istrade | quotes | numeric | Were there any trades on this security
| ClosePrice | quotes | numeric |
| step_price | quotes | numeric | Price increment
| scheme_calc | quotes | numeric |
| yld_ytm_ask | quotes | numeric | Yiled to maturity from ask prices (for bonds)
| yld_ytm_bid | quotes | numeric | Yield to maturity from bid prices (for bonds)
| base_currency | quotes | string | Base instrument currency
| x_agg_futures | quotes | string |
| virt_base_instr | quotes | string |
| x_dsc1_reception | quotes | string | Discount (by office)
| x_short_reception | quotes | string | Is it possible to short the security (by offices)
| TradingSessionSubID | quotes | string |
| TradingReferencePrice | quotes | numeric |
| rate | securities | numeric | Ranking in the search
| id | securities | numeric |
| min_step | securities | string | Minimum price increment
| issuer_country_code | securities | string | Letter code of the issuing country
| exchange_ticker | securities | string | Instrument code on the exchange
| maturity_code | securities | string |
| sector_code | securities | string |
| attributes | securities | JSON string |
| CFICode | attributes | string | CFI code
| min_step | attributes | string | Minimum price increment
| limit_down | attributes | string |
| step_price | attributes | string | Price increment
| base_mkt_id | attributes | string |
| description | attributes | string |
| scheme_calc | attributes | string |
| export_instrument_to_DIB | attributes | string |
| codesub_nm | securities | string |
| bloomberg_id | attributes | string |

#### Examples of instrument type combinations can be found at 	 Instruments details

### Examples of using

## Examples

```json
/**
* Entire list request
* @type {Securities}
*/
var exampleParams = {
    "cmd"    : "getAllSecurities",
    "params" : {}
};

/**
* Page-by-page request
* @type {Securities}
*/
var exampleParams = {
    "cmd"    : "getAllSecurities",
    "params" : {
        "take": 10,
        "skip": 0
    }
};

/**
* Request with sorting by field
* @type {Securities}
*/
var exampleParams = {
    "cmd"    : "getAllSecurities",
    "params" : {
        "take": 10,
        "skip": 0,
        "sort": [{
            "field": "ticker",
            "dir": "ASC"
        }]
    }
};

/**
* Request with filtering
* @type {Securities}
*/
var exampleParams = {
    "cmd"    : "getAllSecurities",
    "params" : {
        "take": 10,
        "skip": 0,
        "filter": {
            "filters": [
                {
                    "field": "ticker",
                    "operator": "eq",
                    "value": "AAPL.US"
                },
                {
                    "field": "instr_type",
                    "operator": "in",
                    "value": "Options"
                }
            ]
        }
    }
};

$.ajax('https://tradernet.com/api/', {
    dataType: "json",
    type: 'POST',
    data: {q: JSON.stringify(exampleParams)},
    success:  function(data){
        console.log(data);
    }
});
```

You can get the list of instruments in JSON format by a direct request to the server, for example
