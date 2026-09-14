# Optimisation de decoupe de tissu

Application desktop Python/PySide6 pour placer des rectangles, triangles,
polygones, cercles et ovales dans un rouleau de tissu de largeur fixe.
Toutes les dimensions sont saisies et sauvegardees en centimetres.

## Installation

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Lancement

```bash
python -m tissue_nesting
```

ou :

```bash
python main.py
```

## Tests

```bash
pytest
```

## Format JSON

```json
{
  "fabric": {
    "width": 140,
    "max_length": 500,
    "fixed_length": null,
    "spacing": 0.5,
    "grain_axis": "lengthwise",
    "unit": "cm",
    "background_image_path": "/chemin/vers/photo-tissu.jpg"
  },
  "pieces": [
    {
      "id": "devant",
      "name": "Devant",
      "kind": "rectangle",
      "quantity": 2,
      "width": 42,
      "height": 76,
      "can_rotate": true,
      "respect_grain": false,
      "allowed_rotations": [0, 180],
      "color": "#5b8def"
    }
  ]
}
```
