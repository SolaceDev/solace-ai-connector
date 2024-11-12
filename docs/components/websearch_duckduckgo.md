# WebSearchDuckDuckGo

Perform a search query on DuckDuckGo.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: websearch_duckduckgo
component_config:
  pretty: <string>
  no_html: <string>
  skip_disambig: <string>
  detail: <string>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| pretty | False | 1 | Beautify the search output. |
| no_html | False | 1 | The number of output pages. |
| skip_disambig | False | 1 | Skip disambiguation. |
| detail | False | False | Return the detail. |


## Component Input Schema

```
<string>
```


## Component Output Schema

```
{
  title:   <string>,
  snippet:   <string>,
  url:   <string>
}
```
| Field | Required | Description |
| --- | --- | --- |
| title | False |  |
| snippet | False |  |
| url | False |  |
