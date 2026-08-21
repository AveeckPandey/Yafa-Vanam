# YAFA VANAM CV validation dataset

This dataset is for evaluation only. It must contain at least 30 consented or open-licensed images: five images for each Fitzpatrick type (I–VI). Do not place customer selfies in this directory or commit them to source control.

Each image is listed in `test_images/manifest.json` with:

- `filename`
- `fitzpatrick_type` (`I`–`VI`)
- `lighting` (`natural`, `indoor`, or `artificial`)
- `device_category` (`smartphone_front`, `smartphone_rear`, or `webcam`)
- `ground_truth_undertone` (`warm`, `cool`, or `neutral`)
- `ground_truth_depth` (`fair`, `light`, `medium`, `tan`, or `deep`)

Use only data whose licence and consent permit this purpose. Candidate sources are the [Chicago Face Database](https://www.chicagofaces.org/), [Diversity in Faces](https://www.researchgate.net/publication/329779697_Diversity_in_Faces_A_Dataset_for_Advancing_the_Study_of_Face_Recognition), and [FairFace](https://github.com/joojs/fairface). Review each source’s current licence, terms, demographic labels, and consent statement before use; do not infer or relabel sensitive characteristics from images.

The validation report must be reviewed for uneven error rates across Fitzpatrick categories, lighting, and device categories. High-confidence mistakes are release blockers. Keep the manifest and generated report in restricted evaluation storage; publish only aggregate results.
