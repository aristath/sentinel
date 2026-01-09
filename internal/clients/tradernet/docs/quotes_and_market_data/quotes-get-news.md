# News on securities.

### Description of the server reply and an example of the reply

#### The request requires authorization. In the request header, you need to pass the cookieSID, received during authorization.

### Examples of using

## Examples

### Browser

```json
/**
 * @type {getNews}
 */
var exampleParams = {
    'cmd':     'getNews',
    'params': {

        'limit': 30,
        'searchFor': 'Apple', // Can be ticker or any word
        'ticker': 'AAPL.US', // If parameter ticker is set, searchFor wlll be ignored and newsfeed will consists only of stories solely based on mentioned ticker
        'storyId': '200199', // If parameter storyId is set, searchFor and Ticker params wlll be ignored and news feed will consists only of the story with required storyId
    }
};


function getNews(searchFor, ticker, storyId, callback) {

    exampleParams['searchFor'] = searchFor;
    exampleParams['ticker'] = ticker;
    exampleParams['storyId'] = storyId;

    $.getJSON('https://tradernet.com/api/', {q: JSON.stringify(exampleParams)}, callback);
}

/**
 *  We get the news feed based on the company name. **/
getNews('Apple', null, null, function(json){
    console.log(json);
});


/**
 *  Get the news feed using the ticker **/
getNews(null, 'AAPL.US', null, function(json){
    console.log(json);
});


/**
 *  Get the news using an id **/
getNews(null, null, 2001200, function(json){
    console.log(json);
});
```
