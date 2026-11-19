# Gera painel_v3/vendor/malha_uf.js: contornos simplificados das 27 UFs (IBGE, via geobr)
# Executar a partir da pasta do projeto: Rscript painel_v3/gera_malha_uf.R
# Requer internet (o geobr baixa a malha estadual do IPEA).
#
# Simplificação: tolerância de 8 km em projeção métrica (SIRGAS 2000 / Policônica),
# suficiente para um mapa do tamanho de um cartão; coordenadas com 3 casas decimais.

suppressPackageStartupMessages({
  library(sf)
  library(geobr)
})

ufs <- suppressMessages(read_state(year = 2020, showProgress = FALSE))
ufs <- st_transform(ufs, 5880)
ufs <- st_simplify(ufs, preserveTopology = TRUE, dTolerance = 8000)
ufs <- st_transform(ufs, 4326)
ufs <- ufs[, c("abbrev_state", "name_state")]
names(ufs)[1:2] <- c("uf", "nome")

tmp <- tempfile(fileext = ".geojson")
st_write(ufs, tmp, driver = "GeoJSON", quiet = TRUE,
         layer_options = "COORDINATE_PRECISION=3")
# O sentido dos contornos (horário/anti-horário) é acertado no painel, ao carregar
geo <- paste(readLines(tmp, warn = FALSE), collapse = "")

writeLines(
  c("// Gerado por painel_v3/gera_malha_uf.R — malha estadual do IBGE (2020), via geobr; simplificada",
    paste0("window.MALHA_UF = ", geo, ";")),
  "painel_v3/vendor/malha_uf.js", useBytes = TRUE
)
cat(sprintf("%d UFs; %.0f KB\n", nrow(ufs), file.size("painel_v3/vendor/malha_uf.js") / 1024))
