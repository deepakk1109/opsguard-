# Terminal 2: serve Strands Decider 2B locally (first run downloads ~9 GB)
.\.venv\Scripts\Activate.ps1
$model = if ($env:DECIDER_MODEL) { $env:DECIDER_MODEL } else { "StrandsAgents/strands-decider-2B-hobson-v21" }
strands-decider serve $model --port 8099
