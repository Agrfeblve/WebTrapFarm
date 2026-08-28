# browser-use Agent

## Running

The agent is started by the `run.sh` script. From this directory, run:

```bash
bash run.sh
```

## Running Modes

Select a mode by editing the `runtime` section in the root `config.json` file before running `bash run.sh`:

| Mode | `use_vision` | `no_dom_filter` |
| --- | --- | --- |
| browser-use-text | `"false"` | `false` |
| browser-use-vision | `"true"` | `false` |
| browser-use-text (no DOM filter) | `"false"` | `true` |
| browser-use-vision (no DOM filter) | `"true"` | `true` |

For example, to run browser-use-vision without the DOM filter, configure:

```json
{
  "runtime": {
    "use_vision": "true",
    "no_dom_filter": true,
    "max_workers": 20
  }
}
```

Then run:

```bash
bash run.sh
```

When `no_dom_filter` is `true`, the complete unfiltered DOM representation is passed to the agent.
