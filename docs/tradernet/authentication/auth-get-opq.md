# Initial object with all the user data.

### Description of server request parameters and a sample response:

#### Request:

```json
{
    "cmd" (string)   : "getOPQ",
    "SID" (string)   : "[SID by authorization]",
    "params" (array) : {}
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| SID |   | string | SID received during the user's authorization
| params |   | array | Request execution parameters

#### Response:

Getting a response if successful.

```json
{
  "OPQ" (array) : {
    "rev"         (int) : 2011111110,
    "init_margin" (int) : 2,
    "brief_nm"    (string) : "000000",
    "reception"   (int) : 1,
    "active"      (int) : 1,
    "quotes" (array) : {
      "q" (array) : [
        {
          "acd" (int) : 0,
          "baf" (int) : 0,
          "bap" (float) : 151.7,
          "bas" (int) : 209,
          "base_contract_code" (string) : "",
          "base_currency" (string) : "",
          "base_ltr" (string) : "FIX",
          "bbf" (int) : 0,
          "bbp" (float) : 151.00,
          "bbs" (float) : 147,
          "c" (string) : "AAPL.US",
          "chg" (float) : 0.65,
          "chg110" (float) : 20.24,
          "chg22" (float) : 3.89,
          "chg220" (float) : 29.67,
          "chg5" (infloatt) : 2.53,
          "ClosePrice" (float) : 151.00,
          "codesub_nm" (string) : "NASDAQ",
          "cpn" (int) : 0,
          "cpp" (int) : 0,
          "dpb" (int) : 0,
          "dps" (int) : 0,
          "emitent_type" (string) : "",
          "fv" (int) : 100,
          "init" (int) : 1,
          "ipo" (int) : "",
          "issue_nb" (string) : "US0378331005",
          "kind" (int) : 1,
          "ltp" (float) : 151.57,
          "ltr" (string) : "FIX",
          "lts" (int) : 76,
          "ltt" (string) : "2021-11-05T10:07:10",
          "marketStatus" (string) : "OPEN",
          "maxtp" (float) : 152.00,
          "min_step" (float) : 0.01,
          "mintp" (float) : 151.00,
          "mrg" (string) : "M",
          "mtd" (string) : "",
          "n" (int) : 2395,
          "name" (string) : "Apple Inc.",
          "name2" (string) : "",
          "ncd" (string) : "",
          "ncp" (int) : 0,
          "op" (float) : 151.00,
          "option_type" (string) : "",
          "otc_instr" (string) : "AAPL.US.OTC",
          "p110" (float) : 125.00,
          "p22" (float) : 145.00,
          "p220" (float) : 116.00,
          "p5" (float) : 147.00,
          "pcp" (float) : 0.43,
          "pp" (float) : 150.92,
          "quote_basis" (string) : "",
          "rev" (int) : 20614034,
          "scheme_calc" (string) : "T2",
          "step_price" (float) : 0.01,
          "strike_price" (int) : 0,
          "trades" (int) : 2715,
          "TradingReferencePrice" (int) : 0,
          "TradingSessionSubID" (string) : "",
          "type" (int) : 1,
          "UTCOffset" (int) : -240,
          "virt_base_instr" (string) : "",
          "vlt" (float) : 1772090810.19,
          "vol" (int) : 11691567,
          "x_agg_futures" (string) : "",
          "x_curr" (string) : "USD",
          "x_currVal" (float) : 71.73,
          "x_descr" (string) : "Apple Inc. is a recognized innovator and experimenter, dictating technological rules and fashion in computer design.",
          "x_dsc1" (int) : 25,
          "x_dsc1_reception" (string) : "0=25.0000,1=25.0000",
          "x_dsc2" (int) : 100,
          "x_dsc3" (int) : 100,
          "x_istrade" (int) : 1,
          "x_lot" (int) : 1,
          "x_max" (float) : 325.05,
          "x_min" (float) : 80.1875,
          "x_min_lot_q" (string) : "",
          "x_short" (int) : 1,
          "x_short_reception" (string) : "0=1,1=1",
          "yld" (int) : 0,
          "yld_ytm_ask" (int) : 0,
          "yld_ytm_bid" (int) : 0
        },
        ...
      ]
    },
    "ps" (array) : {
      "loaded" (bool)  : true,
      "acc"    (array) : [
        {
          "curr" (string) : "USD",
          "currval" (float) : 1,
          "forecast_in" (float) : 0,
          "forecast_out" (float) : 0,
          "t2_in" (float) : 0,
          "t2_out" (float) : 0,
          "s" (float) : 358.00
        },
        ...
      ],
      "pos" (array) : [
        {
          "open_bal" (float) : 100.8,
          "mkt_price" (float) : 13.5,
          "name" (string) : "Apple Inc. is a recognized innovator and experimenter, dictating technological rules and fashion in computer design.",
          "i" (string) : "AAPL.US",
          "t" (int) : 1,
          "scheme_calc" (string) : "T2",
          "instr_id" (int) : ,
          "Yield" (int) : 0,
          "issue_nb" (string) : "",
          "profit_price" (float) : 11.5,
          "acc_pos_id" (int) : 9485,
          "accruedint_a" (int) : 0,
          "acd" (int) : 0,
          "k" (int) : 1,
          "bal_price_a" (float) : 11.78,
          "price_a" (float) : 11.78,
          "base_currency" (string) : "USD",
          "face_val_a" (float) : 0.64,
          "curr" (string) : "USD",
          "go" (int) : 0,
          "profit_close" (float) : -2.8,
          "fv" (int) : 100,
          "vm" (int) : 0,
          "q" (int) : 10,
          "name2" (string) : "Apple Inc. is a recognized innovator and experimenter, dictating technological rules and fashion in computer design.",
          "market_value" (float) : 110,
          "close_price" (float) : 11.588,
          "currval" (int) : 1,
          "s" (float) : 110.8
        },
        ...
      ]
    },
    "orders" (array) : {
      "loaded" (bool) : true,
      "order"  (array) : []
    },
    "sess"      (array) : [],
    "markets"   (array) : {
      "markets" (array) : {
        "t" (string) : "11\/5\/2021 3:01:20 AM",
        "m" (array) : [
          {
            "n" (string) : "FIX",
            "n2" (string) : "FIX",
            "s" (string) : "CLOSE",
            "o" (string) : "10:00:00",
            "c" (string) : "23:50:00",
            "dt" (int) : 0,
            "p" (string) : "09:50:00",
            "post" (string) : "19:00:00",
            "date" (array) : [
              {
                "from" (string) : "0101",
                "to" (string) : "0101",
                "dayoff" (int) : 1,
                "desc" (string) : "New year"
              }
            ],
            "ev" (array) : [
              {
                "id" (string) : "StartGate",
                "t" (string) : "09:20:00",
                "next" (string) : "2021-11-05T09:20:00"
              }
            ]
          }
        ]
      }
    },
    "source"     (string) : "account1",
    "offbalance" (array)  : {
      "net_assets" (int) : 0,
      "pos" (array) : [],
      "acc" (array) : []
    },
    "homeCurrency" (string) : "USD",
    "userLists"    (array)  : {
      "userStockLists" (array) : {
        "default" (array[string]) : [
          "BA.US",
          "MCD.US",
          "AXP.US",
          "MMM.US"
        ]
      },
      "userStockListSelected" (string) : "default",
      "stocksArray" (array[string]) : [
        "MCD.US",
        "AXP.US",
        "MMM.US"
      ]
    },
    "NO_ORDER_GROWLS" (string) : null,
    "userInfo" (array) : {
      "id" (int) : 100000000,
      "group_id" (int) : 1,
      "login" (string) : "User",
      "lastname" (string) : "User",
      "firstname" (string) : "User",
      "middlename" (string) : "User",
      "last_first_middle_name" (string) : "User User User",
      "first_last_name" (string) : "User User",
      "email" (string) : "User@User.com",
      "mod_tmstmp" (string) : "2021-11-05 08:08:42.2293",
      "rec_tmstmp" (string) : "2019-07-23 12:04:05",
      "last_visit_tmstmp" (string) : "2021-10-01 16:46:55",
      "umod_tmstmp" (string) : "2021-01-12 12:09:09",
      "date_tsmod" (string) : "2021-07-07 11:35:00",
      "date_last_request" (string) : "2021-10-05 17:00:23",
      "f_active" (int) : 1,
      "trader_systems_id" (string) : "000000",
      "client_id" (int) : 30000000,
      "f_demo" (int) : 0,
      "birthday" (string) : "1971-01-01",
      "sex" (string) : null,
      "citizenship" (string) : "Europe",
      "citizenship_code" (string) : "EU",
      "status" (string) : "Client",
      "type" (string) : "Natural person",
      "status_id" (int) : 10013,
      "utm_campaign" (string) : null,
      "auth_login" (string) : "User@User.com",
      "settlement_pair" (string) : "{1000000000}",
      "description" (string) : null,
      "tel" (string) : "+49999998811",
      "fb_uid" (string) : null,
      "robot" (int) : 0,
      "minimum_investment" (string) : null,
      "language" (string) : "en",
      "additional_status" (int) : 11278,
      "profilename" (string) : "User",
      "reception" (int) : 1,
      "reception_service" (int) : 1,
      "briefnm_additional" (string) : null,
      "manager_user_id" (int) : 111111111,
      "google_id" (string) : null,
      "details" (array) : {
        "iis" (string) : "regular",
        "push" (array) : {
          "android_tn" (string) : "eV"
        },
        "comment" (string) : "b/w scan",
        "smev_sms" (string) : "12131231",
        "statuses" (array) : {
          "0" (string) : "2019-07-23",
          "1" (string) : "2019-08-02",
          "10012" (string) : "2019-08-13",
          "10013" (string) : "2019-08-14",
          "10815" (string) : "2019-08-02",
          "10816" (string) : "2019-08-13",
          "10817" (string) : "2019-07-23",
          "10832" (string) : "2019-08-13"
        },
        "mkt_codes" (array) : {
          "30000000001" (string) : "CY0184",
          "30000000002" (string) : "U702U6",
        },
        "telegram_id" (string) : "11111111",
        "telegram_bot" (bool) : true,
        "Date register" (string) : "2020-07-01",
        "isLeadAccount" (bool) : true,
        "Date open real" (string) : "2019-08-14",
        "passport_check" (string) : "expired",
        "mail_subscription" (int) : 1,
        "ffinbank_requisites" (array) : {
          "date_mod" (int) : "05.11.2021 08:08:42",
          "response" (array) : {
            "Accounts" (array) : [
              {
                "Number" (string) : "Not found",
                "Passport" (string) : "1511 7111111"
              }
            ]
          }
        },
        "initial_telegram_id" (string) : "21111111111",
        "passport_check_date" (string) : "2021-11-05 01:43:42",
        "lastShownDateMessage" (array) : {
          "e2V" (int) : 111213123123
        },
        "utm_campaign - to Real" (string) : null,
        "utm_campaign - Register" (string) : "",
        "telegram_last_updated_at" (int) : 1123123123123,
        "personal_anketa_last_date" (string) : "2021-07-07 00:00:00",
        "detected_reception_service" (int) : 1
      },
      "inn" (string) : "31111111111111111111",
      "country" (string) : null,
      "original_client_user_id" (int) : 100000000,
      "contact_id" (string) : null,
      "role_name" (string) : "user",
      "role" (int) : 1,
      "date_open_real" (string) : "2019-01-14",
      "numdoc" (string) : "7000000",
      "docseries" (string) : "1500",
      "regname" (string) : "",
      "regcode" (string) : "000-000",
      "datedoc" (string) : "2008-01-14T00:00:00",
      "documents" (string) : "{}",
      "bornplace" (string) : "",
      "f_kval" (int) : 0,
      "account_block_date" (string) : "2021-01-06 02:52:26",
      "client_date_close" (string) : null,
      "date_client_doc_received" (string) : "2019-01-14",
      "iis" (string) : "regular",
      "isleadaccount" (string) : "true",
      "mkt_codes" (string) : "{\"30000000012\": \"56896\"}",
      "object_type" (string) : "user",
      "registered_at_domain" (string) : "tradernet.com",
      "email_confirm" (int) : 1,
      "blocks_count" (int) : 1,
      "isIpoAvailable" (bool) : true,
      "currentlyAvailableIpos" (int) : 2,
      "isSubscribedToNewIpos" (int) : 0,
      "isStockBonusAvailable" (bool) : false,
      "stockBonusIdKey" (bool) : false,
      "kassaNovaInvestCardAvailable" (bool) : false,
      "messages_counts" (array) : {
        "no_read" (int) : 5,
        "all" (int) : 300
      },
      "tariffDetails" (array) : {
        "id" (int) : 79,
        "name" (string) : "Standard",
        "curr" (string) : "USD"
      }
    },
    "userOptions" (array) : {
      "cost_open" (int) : 0,
      "cost_last" (int) : 1,
      "cost_low" (int) : 0,
      "cost_high" (int) : 0,
      "bid_last" (int) : 0,
      "offer_last" (int) : 0,
      "volume" (int) : 1,
      "graphic_type" (int) : 1,
      "graphic_format" (string) : "Candlestick",
      "period" (string) : "Y1",
      "time_period" (string) : "00:00 - 23:59",
      "interval" (string) : "D1",
      "date_from" (string) : "13.05.2019",
      "date_to" (string) : "13.08.2019",
      "api_secret" (string) : "",
      "f_transaction" (int) : 0,
      "f_compare_index" (int) : 0,
      "graphic_indicators" (string) : "&i00",
      "profile_type" (int) : 1,
      "showPortfolioBlock" (int) : 1,
      "pageFirstTabOpen" (int) : 0,
      "cover" (string) : "\/layout\/img\/bg.png",
      "access_cost" (int) : 10,
      "theme" (string) : "light",
      "showTransactionsMode" (string) : "2",
      "gridPortfolio" (array) : [
        "type",
        "code",
        "instr_name"
      ]
    }
  }
}
```

We get an answer in case of failure

```json
// Common error
{
    "errMsg" : "Bad json",
    "code"   : 2
}

// Method error
{
    "error" : "User is not found",
    "code"  : 7
}
```

**Description of response parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| OPQ |   | array[][] | All user data

### Examples of using

## Examples

### JS (jQuery)

```json
/**
 * @type {getOPQ}
 */
var exampleParams = {
    'cmd'    : 'getOPQ',
    "SID"    : "[SID by authorization]",
    'params' : {}
};


function getOPQ(callback) {
    $.getJSON('https://tradernet.com/api/', {q: JSON.stringify(exampleParams)}, callback);
}

/**
 *  Get the object **/
getOPQ (function(json) {
    console.log(json);
});
```
