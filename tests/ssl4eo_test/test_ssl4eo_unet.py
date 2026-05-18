"""
Test SSL4EO-L pretrained weights wired into a U-Net for Landsat segmentation.

Goal: sanity check — load SSL4EO-L weights into a ResNet18 U-Net encoder and run
forward on dummy chips on CPU or GPU.

Usage:
    python test_ssl4eo_unet.py --sensor oli_sr --chip 256 --classes 5
    python test_ssl4eo_unet.py --device cuda   # fuerza GPU local si hay CUDA
    python test_ssl4eo_unet.py --device cpu    # solo CPU (ej. cluster sin GPU)
    python test_ssl4eo_unet.py --sensor etm_sr --chip 256 --classes 5
    python test_ssl4eo_unet.py --sensor tm_toa --chip 256 --classes 5

Notes on SSL4EO-L checkpoints in torchgeo (verified May 2026):
    - LANDSAT_OLI_SR_MOCO   -> L8/L9  Level-2 SR, 7 bands
    - LANDSAT_OLI_SR_SIMCLR -> idem
    - LANDSAT_OLI_TIRS_TOA_MOCO / SIMCLR -> L8/L9 TOA, 11 bands
    - LANDSAT_ETM_SR_MOCO   -> L7     Level-2 SR, 6 bands
    - LANDSAT_ETM_SR_SIMCLR -> idem
    - LANDSAT_ETM_TOA_MOCO / SIMCLR -> L7 TOA, 9 bands
    - LANDSAT_TM_TOA_MOCO / SIMCLR  -> L4/L5 TOA, 7 bands (NO HAY SR para TM)

Para tu pipeline (1996-2025 Landsat C2 Level-2 SR):
    - L5 (1996-2012): no hay pesos SR, hay que usar TM_TOA_MOCO o homogeneizar
      bandas y reusar OLI_SR_MOCO con random init en bandas faltantes.
    - L7 (1999-2025): ETM_SR_MOCO directo.
    - L8/L9 (2013-2025): OLI_SR_MOCO directo.
"""

import argparse
import time

import torch
import segmentation_models_pytorch as smp
from torchgeo.models import ResNet18_Weights


# Mapa sensor -> enum de torchgeo
WEIGHT_MAP = {
    "oli_sr":   ResNet18_Weights.LANDSAT_OLI_SR_MOCO,
    "etm_sr":   ResNet18_Weights.LANDSAT_ETM_SR_MOCO,
    "tm_toa":   ResNet18_Weights.LANDSAT_TM_TOA_MOCO,
    "oli_toa":  ResNet18_Weights.LANDSAT_OLI_TIRS_TOA_MOCO,
    "etm_toa":  ResNet18_Weights.LANDSAT_ETM_TOA_MOCO,
}


def build_unet_with_ssl4eo(sensor: str, n_classes: int) -> tuple[torch.nn.Module, int]:
    """
    Build a U-Net with ResNet18 encoder initialized from SSL4EO-L weights.

    Returns:
        model: ready-to-finetune U-Net (encoder pretrained, decoder + head random).
        in_chans: number of input channels expected by the model.
    """
    weights = WEIGHT_MAP[sensor]
    in_chans = weights.meta["in_chans"]
    bands = weights.meta.get("bands", "n/a")
    print(f"[info] sensor={sensor}  in_chans={in_chans}  bands={bands}")

    # 1) Build a vanilla U-Net with smp. encoder_weights=None: we will inject
    #    SSL4EO weights manually. in_channels matches the SSL4EO checkpoint
    #    so the first conv layer has the right shape.
    model = smp.Unet(
        encoder_name="resnet18",
        encoder_weights=None,
        in_channels=in_chans,
        classes=n_classes,
    )

    # 2) Pull the SSL4EO state_dict and load it into the encoder. The encoder
    #    in smp uses timm-style naming (conv1, bn1, layer1..4), which matches
    #    what torchgeo / timm publish. strict=False because we are NOT loading
    #    the classification head (fc) — we only want the conv tower.
    state_dict = weights.get_state_dict(progress=True)
    result = torch.nn.Module.load_state_dict(
        model.encoder, state_dict, strict=False
    )
    missing, unexpected = result.missing_keys, result.unexpected_keys

    # Sanity: the encoder backbone keys should all be matched. The only
    # 'missing' keys would be smp-specific buffers (rare), and the only
    # 'unexpected' keys would be fc.weight/fc.bias from the pretraining
    # classification head (not used here).
    print(f"[info] loaded SSL4EO-L weights into encoder")
    print(f"       missing keys (expected ~0):     {len(missing)}")
    print(f"       unexpected keys (expected: fc.*): {len(unexpected)}")
    if missing:
        print(f"       first missing: {missing[:3]}")
    if unexpected:
        print(f"       first unexpected: {unexpected[:3]}")

    return model, in_chans


def resolve_device(kind: str) -> torch.device:
    """Pick torch.device from CLI: auto prefers CUDA when available."""
    if kind == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if kind == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("Se pidio --device cuda pero CUDA no esta disponible.")
        return torch.device("cuda")
    return torch.device("cpu")


def forward_benchmark(
    model: torch.nn.Module, in_chans: int, chip: int, device: torch.device
) -> None:
    """Forward pass benchmark on the given device (syncs CUDA for timing)."""
    model.eval()
    n_threads = torch.get_num_threads()
    use_cuda = device.type == "cuda"

    for bs in (1, 2, 4):
        x = torch.randn(bs, in_chans, chip, chip, device=device)

        with torch.no_grad():
            _ = model(x)
        if use_cuda:
            torch.cuda.synchronize()

        times = []
        for _ in range(3):
            if use_cuda:
                torch.cuda.synchronize()
            t0 = time.perf_counter()
            with torch.no_grad():
                y = model(x)
            if use_cuda:
                torch.cuda.synchronize()
            times.append(time.perf_counter() - t0)
        med = sorted(times)[1]
        per_chip = med / bs * 1000
        thr_tag = n_threads if device.type == "cpu" else "-"
        print(f"[bench] bs={bs}  chip={chip}  device={device.type}  threads={thr_tag}  "
              f"median={med*1000:7.1f} ms  per_chip={per_chip:6.1f} ms  "
              f"out_shape={tuple(y.shape)}")


def count_params(model: torch.nn.Module) -> None:
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"[info] params total: {total/1e6:.2f}M  trainable: {trainable/1e6:.2f}M")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sensor", choices=list(WEIGHT_MAP.keys()),
                        default="oli_sr",
                        help="Cual checkpoint SSL4EO-L cargar")
    parser.add_argument("--chip", type=int, default=256,
                        help="Lado del chip cuadrado, multiplo de 32")
    parser.add_argument("--classes", type=int, default=5,
                        help="Numero de clases del decoder")
    parser.add_argument("--threads", type=int, default=4,
                        help="Numero de threads CPU (solo afecta ops en CPU)")
    parser.add_argument(
        "--device",
        choices=("auto", "cuda", "cpu"),
        default="auto",
        help="auto: CUDA si hay GPU, si no CPU. En cluster sin GPU usar auto o cpu.",
    )
    args = parser.parse_args()

    assert args.chip % 32 == 0, "chip debe ser multiplo de 32 para U-Net/ResNet"
    device = resolve_device(args.device)
    torch.set_num_threads(args.threads)

    print(f"=== SSL4EO-L + U-Net sanity test ===")
    cuda_info = ""
    if device.type == "cuda":
        cuda_info = f"  cuda={torch.cuda.get_device_name(torch.cuda.current_device())}"
    print(f"torch={torch.__version__}  smp={smp.__version__}  "
          f"device={device}  threads(CPU)={torch.get_num_threads()}{cuda_info}")

    model, in_chans = build_unet_with_ssl4eo(args.sensor, args.classes)
    model = model.to(device)
    count_params(model)
    forward_benchmark(model, in_chans, args.chip, device)
    print("=== OK ===")


if __name__ == "__main__":
    main()
