# Obtaining data on the client's cash flow

### Description of server request parameters and a sample response:

The method enables receiving data on client's cash flow.

#### Request:

```json
{
    "cmd" (string)   : "getUserCashFlows",
    "SID" (string)   : "[SID by authorization]",
    "params" (array) : {
        "user_id"        (int|null)       : <User Id>,
        "groupByType"    (int|null)       : 1,
        "take"           (int|null)       : 10,
        "skip"           (int|null)       : 5,
        "without_refund" (int|null)       : 1,
        "filters"        (array[][]|null) : [
            {
                'field'    (string) : 'type_code', // filter field
                'operator' (string) : 'neq',       // filter statement
                'value'    (string) : 'your value' // filter value
            },
            ...
        ],
        "sort"          (array[][]|null)  : [
            {
                'field' (string) : 'type_code', // sorting field
                'dir'   (string) : 'DESC'        // sorting order, only accepts ASC or DESC
            },
            ...
        ]
    }
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| SID |   | string | SID received during the user's authorization
| params |   | array | Request execution parameters
| params | user_id | int|null | Client ID to find the report. Optional parameter
| params | groupByType | int|null #### Response:

Getting a response if successful.

```json
            params
            cash_totals
            int|null


            params
            hide_limits
            int|null


            params
            take
            int|null
            Output data amount. Optional parameter


            params
            skip
            int|null
            Output data offset. Optional parameter


            params
            without_refund
            int|null


            params
            filters
            array|null
            *Output data filter. Optional parameter


            params
            sort
            array|null
            Output data sorting. Optional parameter





        * — Output data filter
        Field values usable for filtering. Field with key "field":

        The same fields can be used when sorting

        Filter statement values. Field with key "operator":






{
  "total"    (int)   : 10,
  "cashflow" (array) : {
      {
        "id"             (int)              : "9f0a11cc61",
        "type_code"      (string)           : "commission_for_trades",
        "icon"           (string)           : "commission",
        "date"           (string|datetime)  : "2021-06-28",
        "sum"            (string)           : "-3.00",
        "comment"        (string)           : "(Trade 1515 2021-06-28 12:21:35)",
        "currency"       (string)           : "USD",
        "type_code_name" (string)           : " type code name "
      },
      ...
  },
  "limits" (array) : {
      USD (array) : {
        "minimum"      (float) : 50.0,
        "multiplicity" (float) : 1.0,
        "maximum"      (float) : 100.0,
      },
      ...
  },
  "cash_totals": {
      "currency" (string) : "USD",
      "list" (array) : [
          {
              "date" (datetime) : "2021-06-28",
              "sum" (float)     : 500.62
          },
          {
              "date" (datetime) : "2021-06-29",
              "sum" (float)     : 1080.97
          }
      ]
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
```

**Description of response parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| total |   | int | Total data
| cashflow |   | array | Cash flow list

### Examples of using

## Examples

### JS (jQuery)

```json
/**
 * @type {getUserCashFlows}
 */
var exampleParams = {
    "cmd"    : "getUserCashFlows",
    "SID"    : "[SID by authorization]",
    "params"  : {
        "user_id"      : <User Id>,
        "groupByType"  : 1,
        "take"         : 10,
        "skip"         : 5,
        "filters"      : [
            {
                'field'    : 'type_code', // filter field
                'operator' : 'neq',       // filter statement
                'value'    : 'your value' // filter value
            }
        ],
        "sort"         : [
            {
                'field' : 'type_code', // sorting field
                'dir'   : 'DESC'        // sorting order, only accepts ASC or DESC
            }
        ]
    }
};

function getUserCashFlows(callback) {
    $.getJSON("https://tradernet.com/api/", {q: JSON.stringify(exampleParams)}, callback);
}

/**
 * Get the object **/
getUserCashFlows(function(json){
    console.log(json);
});
```
