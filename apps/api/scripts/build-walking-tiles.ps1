param(
  [Parameter(Mandatory = $true)] [string] $Pbf,
  [Parameter(Mandatory = $true)] [string] $Destination,
  [double] $North = 52.38,
  [double] $South = 52.05,
  [double] $East = 21.36,
  [double] $West = 20.76,
  [int] $Grid = 4,
  [switch] $Merge
)

$ErrorActionPreference = 'Stop'
$culture = [Globalization.CultureInfo]::InvariantCulture
$apiRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $apiRoot '.venv\Scripts\python.exe'
$tilesDirectory = Join-Path (Split-Path -Parent $Destination) 'tiles'
New-Item -ItemType Directory -Force $tilesDirectory | Out-Null

$tileWidth = ($East - $West) / $Grid
$tileHeight = ($North - $South) / $Grid
$overlap = 0.002
$tilePaths = [System.Collections.Generic.List[string]]::new()

for ($column = 0; $column -lt $Grid; $column++) {
  for ($row = 0; $row -lt $Grid; $row++) {
    $tileWest = [Math]::Max($West, $West + $column * $tileWidth - $overlap)
    $tileEast = [Math]::Min($East, $West + ($column + 1) * $tileWidth + $overlap)
    $tileSouth = [Math]::Max($South, $South + $row * $tileHeight - $overlap)
    $tileNorth = [Math]::Min($North, $South + ($row + 1) * $tileHeight + $overlap)
    $tile = Join-Path $tilesDirectory "tile-$column-$row.graphml"
    Write-Output "Building walking tile $column,$row"
    & $python -u -m app.walking $tile --pbf $Pbf --north $tileNorth.ToString($culture) --south $tileSouth.ToString($culture) --east $tileEast.ToString($culture) --west $tileWest.ToString($culture)
    if ($LASTEXITCODE -ne 0) { throw "Walking tile $column,$row failed with exit code $LASTEXITCODE" }
    $tilePaths.Add($tile)
  }
}

if ($Merge) {
  Write-Output 'Merging walking tiles'
  & $python -u -m app.walking $Destination --merge $tilePaths
  if ($LASTEXITCODE -ne 0) { throw "Walking graph merge failed with exit code $LASTEXITCODE" }
}
