# Vela Integration — Critical Additions

> **Document purpose:** Address gaps identified in the initial documentation set.
> **Related:** `01-ecosystem-vision.md`, `02-processbot-spec.md`, `03-deploy-bridge.md`

---

## Gap 1: Missing Sequence Diagrams

### 1.1 ProcessBot Vision: Photo → Process (Full Flow)

```
User                Vela FE          Vela BE          AI Router        ProcessBot       Aether Billing
 │                    │                │                 │                │                 │
 │  1. Upload photo   │                │                 │                │                 │
 │───────────────────►│                │                 │                │                 │
 │                    │  2. POST       │                 │                │                 │
 │                    │  /generate     │                 │                │                 │
 │                    │───────────────►│                 │                │                 │
 │                    │                │                 │                │                 │
 │                    │                │  3. Validate    │                │                 │
 │                    │                │  (size/type)    │                │                 │
 │                    │                │                 │                │                 │
 │                    │                │  4. Check       │                │                 │
 │                    │                │  credits ──────────────────────────────────────────►
 │                    │                │  ◄──────────────────────────────────────────  OK   │
 │                    │                │                 │                │                 │
 │                    │                │  5. Preprocess  │                │                 │
 │                    │                │  image ────────────────────────►│                 │
 │                    │                │  (resize→2048px) │                │                 │
 │                    │                │                 │                │                 │
 │                    │                │  6. Select model │                │                 │
 │                    │                │────────────────►│                │                 │
 │                    │                │  ◄── local/cloud │                │                 │
 │                    │                │                 │                │                 │
 │                    │                │  7. Vision call │                │                 │
 │                    │                │────────────────────────────────►│                 │
 │                    │                │  image + prompt  │                │                 │
 │                    │                │                 │                │                 │
 │                    │                │  8. Streaming    │                │                 │
 │                    │                │  tokens ───────────────────────────────────────────►
 │                    │                │                 │                │                 │
 │                    │                │  9. Raw JSON ◄──│────────────────│                 │
 │                    │                │  {blocks: [...],│                │                 │
 │                    │                │   connections}   │                │                 │
 │                    │                │                 │                │                 │
 │                    │                │  10. Block-match │                │                 │
 │                    │                │  (fuzzy→catalog) │                │                 │
 │                    │                │                 │                │                 │
 │                    │                │  11. Auto-layout │                │                 │
 │                    │                │  (Dagre)         │                │                 │
 │                    │                │                 │                │                 │
 │                    │                │  12. Generate    │                │                 │
 │                    │                │  pages            │                │                 │
 │                    │                │                 │                │                 │
 │                    │                │  13. Deduct      │                │                 │
 │                    │                │  credits ──────────────────────────────────────────►
 │                    │                │  ◄────────────────────────────────────── committed │
 │                    │                │                 │                │                 │
 │                    │  14. Response  │                 │                │                 │
 │                    │  ProcessDef +  │                 │                │                 │
 │                    │  billing info  │                 │                │                 │
 │                    │◄───────────────│                 │                │                 │
 │                    │                │                 │                │                 │
 │  15. Render        │                │                 │                │                 │
 │  FlowEditor canvas │                │                 │                │                 │
 │◄───────────────────│                │                 │                │                 │
 │                    │                │                 │                │                 │
 │  16. User edits,   │                │                 │                │                 │
 │  validates, saves  │                │                 │                │                 │
 │───────────────────►│                │                 │                │                 │
```

### 1.2 Deploy: Vela → Aether Instance

```
Vela BE           Aether Auth       DeployService     Provisioning    Billing      Channels
 │                    │                 │                 │              │             │
 │  1. M2M JWT        │                 │                 │              │             │
 │  (shared secret)   │                 │                 │              │             │
 │───────────────────►│                 │                 │              │             │
 │  ◄── verified OK   │                 │                 │              │             │
 │                    │                 │                 │              │             │
 │  2. POST /deploy   │                 │                 │              │             │
 │─────────────────────────────────────►│                 │              │             │
 │                    │                 │                 │              │             │
 │                    │                 │  3. Validate     │              │             │
 │                    │                 │  manifest        │              │             │
 │                    │                 │  (schema+limits) │              │             │
 │                    │                 │                 │              │             │
 │                    │                 │  4. Create       │              │             │
 │                    │                 │  Tenant ────────►│              │             │
 │                    │                 │  ◄── tenant_id   │              │             │
 │                    │                 │                 │              │             │
 │                    │                 │  5. Provision    │              │             │
 │                    │                 │────────────────►│              │             │
 │                    │                 │                 │  DB schema   │             │
 │                    │                 │                 │  Redis keys  │             │
 │                    │                 │                 │  Default     │             │
 │                    │                 │                 │  roles       │             │
 │                    │                 │  ◄── done       │              │             │
 │                    │                 │                 │              │             │
 │                    │                 │  6. Seed process │              │             │
 │                    │                 │  blocks+conns    │              │             │
 │                    │                 │  pages+routes    │              │             │
 │                    │                 │                 │              │             │
 │                    │                 │  7. Activate     │              │             │
 │                    │                 │  subscription ─────────────────────────────►
 │                    │                 │  ◄── trialing    │              │             │
 │                    │                 │                 │              │             │
 │                    │                 │  8. Configure    │              │             │
 │                    │                 │  channels ───────────────────────────────────►
 │                    │                 │  ◄── active      │              │             │
 │                    │                 │                 │              │             │
 │                    │                 │  9. Create owner │              │             │
 │                    │                 │  + invite link   │              │             │
 │                    │                 │                 │              │             │
 │  10. Response      │                 │                 │              │             │
 │  ◄──────────────────────────────────│                 │              │             │
 │  tenant_id + URLs  │                 │                 │              │             │
 │  + owner_invite    │                 │                 │              │             │
```

### 1.3 M2M Auth Handshake + Rotation

```
Vela BE                              Aether BE                Vault/Config
 │                                      │                         │
 │  1. Sign JWT                         │                         │
 │  {                                   │                         │
 │    sub: "vela.aether.local",         │                         │
 │    iss: "vela.aether.local",         │                         │
 │    scope: "deploy:write",            │                         │
 │    iat: now, exp: now+5m,           │                         │
 │    jti: random-nonce                 │                         │
 │  }                                   │                         │
 │                                      │                         │
 │  2. POST /api/v1/deploy ────────────►│                         │
 │     Authorization: Bearer <jwt>     │                         │
 │                                      │                         │
 │                                      │  3. Verify JWT          │
 │                                      │  ├── signature (HS256)  │
 │                                      │  ├── exp not passed     │
 │                                      │  ├── iss matches        │
 │                                      │  ├── scope sufficient   │
 │                                      │  └── jti not replayed   │
 │                                      │                         │
 │                                      │  4. Log audit           │
 │                                      │  {service, action, jti, │
 │                                      │   ip, timestamp}        │
 │                                      │                         │
 │  5. Response ◄───────────────────────│                         │
 │                                      │                         │
 │  ═══════════ KEY ROTATION ═══════════                          │
 │                                      │                         │
 │  6. Generate new key pair ────────────────────────────────────►
 │  ◄── key_v2, key_v1 (grace)          │                         │
 │                                      │                         │
 │  7. Announce rotation                │                         │
 │     X-Key-Version: v2 ──────────────►│                         │
 │                                      │                         │
 │                                      │  8. Accept both         │
 │                                      │  v1 (grace 24h)         │
 │                                      │  v2 (current)           │
 │                                      │                         │
 │  9. Next deploy with v2 ────────────►│                         │
 │                                      │                         │
 │  10. After 24h: revoke v1 ───────────────────────────────────►│
```

---

## Gap 2: Vision Pipeline — Poor Image Quality Strategy

### 2.1 Image Quality Tiers

| Tier | Description | Strategy |
|------|-------------|----------|
| **A — Clean** | Digital diagram (Draw.io, Visio), high contrast, 90° angle | Direct vision call, max confidence |
| **B — Photo** | Photo of whiteboard/paper, good lighting, slight angle (<15°) | Perspective correction → vision call |
| **C — Poor** | Blurry, low light, steep angle, handwriting | Multi-step: enhance → OCR → structure inference |
| **D — Unusable** | Too dark, too blurry, no diagram visible | Reject with guidance: «Сфоткайте ровнее, при хорошем свете» |

### 2.2 Preprocessing Pipeline by Tier

```python
async def preprocess_image(image: bytes, mime_type: str) -> PreprocessedImage:
    """Smart preprocessing based on image quality assessment."""

    # 1. Quality assessment
    quality = await assess_quality(image)
    # Returns: {tier, angle, blur_score, contrast, lighting, has_diagram}

    tier = quality.tier

    if tier == ImageQualityTier.D_UNUSABLE:
        raise UnusableImageError(
            reasons=quality.issues,
            guidance=[
                "Сфотографируйте схему при хорошем освещении",
                "Держите камеру ровно, без наклона",
                "Убедитесь что схема в фокусе",
            ]
        )

    # 2. Apply corrections
    pipeline = [
        ImagePreprocessingStep.PERSPECTIVE_CORRECT,  # if angle > 5°
        ImagePreprocessingStep.CONTRAST_ENHANCE,     # if low contrast
        ImagePreprocessingStep.DENOISE,              # if blur_score > threshold
        ImagePreprocessingStep.BINARIZE,             # if photo of paper/board
    ]

    if tier == ImageQualityTier.C_POOR:
        pipeline.insert(0, ImagePreprocessingStep.SUPER_RESOLUTION)

    processed = await apply_pipeline(image, pipeline)

    return processed


@dataclass
class ImageQuality:
    tier: ImageQualityTier
    angle: float                # degrees from perpendicular
    blur_score: float           # 0.0 (sharp) to 1.0 (unusable)
    contrast: float             # 0.0 (flat) to 1.0 (high)
    lighting: float             # 0.0 (dark) to 1.0 (bright)
    has_diagram: bool           # does image contain a diagram at all?
    issues: list[str]           # human-readable issues
```

### 2.3 OCR Strategy for Handwritten Text

```python
async def ocr_handwritten_text(image: bytes, regions: list[BoundingBox]) -> list[TextRegion]:
    """Two-stage OCR: first try to find digital text, then handwriting."""

    results = []

    for region in regions:
        crop = crop_image(image, region)

        # Stage 1: Digital text (fast, cheap)
        text = await ocr_digital(crop)

        if text.confidence > 0.8 and text.is_not_garbage:
            results.append(text)
            continue

        # Stage 2: Handwriting OCR (slower, more expensive)
        text = await ocr_handwriting(crop)  # Uses TrOCR or similar

        if text.confidence > 0.5:
            results.append(text)
        else:
            # Stage 3: Flag for manual input
            results.append(TextRegion(
                text="[не распознано]",
                confidence=0.0,
                needs_manual_input=True,
                bbox=region,
            ))

    return results
```

---

## Gap 3: Deploy Failure Recovery (SAGA Pattern)

### 3.1 Compensating Transactions

Deploy has 8 steps. If step N fails, we must undo steps 1..N-1.

```python
class DeploySAGA:
    """SAGA orchestrator with compensating transactions."""

    STEPS = [
        # (step_name, forward_fn, compensate_fn, critical)
        ("validate_manifest",  validate,  noop,            False),
        ("create_tenant",      create_tn, delete_tenant,   True),
        ("provision_tenant",   provision, deprovision,     True),
        ("seed_process",       seed_proc, unseed_process,  False),
        ("seed_pages",         seed_page, unseed_pages,    False),
        ("activate_sub",       activate,  cancel_sub,      False),
        ("config_channels",    config_ch, deconfig_ch,     False),
        ("create_owner",       create_own, delete_owner,   False),
    ]

    async def execute(self, manifest: DeployManifest) -> DeployResult:
        completed = []

        try:
            for name, forward, compensate, critical in self.STEPS:
                try:
                    result = await forward(manifest, completed)
                    completed.append((name, compensate, result))
                except Exception as e:
                    if critical:
                        raise DeployFailedError(f"Critical step '{name}' failed", e)
                    else:
                        # Non-critical: log warning, continue
                        logger.warning(f"Non-critical step '{name}' failed: {e}")
                        self.warnings.append(f"{name}: {e}")

            return DeployResult(
                status="deployed",
                tenant_id=completed[1][2].tenant_id,
                warnings=self.warnings,
            )

        except Exception as e:
            # Compensate in reverse order
            logger.error(f"Deploy failed at step '{name}': {e}")
            await self._compensate(completed)
            raise

    async def _compensate(self, completed: list):
        """Undo completed steps in reverse order."""
        for name, compensate, result in reversed(completed):
            try:
                await compensate(result)
                logger.info(f"Compensated: {name}")
            except Exception as ce:
                logger.critical(
                    f"Compensation failed for '{name}'! Manual intervention needed.",
                    extra={"step": name, "result": result, "error": str(ce)}
                )
                # Alert operations team
                await alert_ops(f"Deploy compensation failed at step '{name}'")
```

### 3.2 Recovery States

```
DEPLOY STATUS STATE MACHINE:

[START]
   │
   ▼
[VALIDATING] ──── failure ──► [REJECTED] (no compensation needed)
   │
   ▼
[PROVISIONING] ── failure ──► [COMPENSATING] ──► [ROLLED_BACK]
   │                                                   │
   ▼                                                   │
[SEEDING] ────── failure ──► [COMPENSATING] ──────────┘
   │                                                   │
   ▼                                                   │
[ACTIVATING] ─── failure ──► [COMPENSATING] ──────────┘
   │
   ▼
[LIVE] ◄── normal state
   │
   ▼
[UPDATING] ───── failure ──► [ROLLBACK_VERSION]
   │
   ▼
[SUSPENDED] ─── resume ──► [LIVE]
   │
   ▼
[DELETED] (soft) ─── retention_period ──► [PURGED] (hard)
```

---

## Gap 4: Test Strategy

### 4.1 Vision Pipeline Testing

```
tests/
├── fixtures/
│   ├── images/
│   │   ├── tier-a-clean-diagram.png       # Digital, perfect
│   │   ├── tier-b-photo-whiteboard.jpg    # Photo, good light
│   │   ├── tier-c-blurry-handwriting.jpg  # Poor quality
│   │   ├── tier-d-unusable-dark.jpg       # Should reject
│   │   ├── no-diagram-landscape.jpg       # Should reject (no diagram)
│   │   └── complex-50-blocks.png          # Boundary: exactly 50 blocks
│   │
│   └── expected/
│       ├── tier-a-expected.json           # Expected ProcessDefinition
│       ├── tier-b-expected.json
│       └── tier-c-expected.json
│
├── test_preprocessing.py
│   ├── test_quality_assessment_tiers()
│   ├── test_perspective_correction()
│   ├── test_contrast_enhancement()
│   ├── test_reject_unusable()
│   └── test_reject_no_diagram()
│
├── test_vision_pipeline.py
│   ├── test_clean_diagram_accuracy()
│   ├── test_photo_accuracy()
│   ├── test_poor_quality_degraded_accuracy()
│   ├── test_block_count_limit()
│   └── test_handwriting_ocr_fallback()
│
├── test_block_matching.py
│   ├── test_exact_match()
│   ├── test_fuzzy_match_ru()
│   ├── test_unmatched_blocks()
│   └── test_synonym_mapping()
│
├── test_auto_layout.py
│   ├── test_simple_linear()
│   ├── test_branching()
│   ├── test_nested_blocks()
│   └── test_no_overlap()
│
└── test_billing.py
    ├── test_credit_check_insufficient()
    ├── test_credit_deduction()
    ├── test_streaming_billing()
    └── test_refund_on_failure()
```

### 4.2 Accuracy Benchmarks

```python
# benchmarks/vision_accuracy.py

async def benchmark_vision_accuracy():
    """Run accuracy benchmark against labeled dataset."""

    dataset = load_dataset("vela-process-diagrams-v1")  # 100 hand-labeled images

    metrics = {
        "block_detection": {"correct": 0, "total": 0},
        "block_type_matching": {"correct": 0, "total": 0},
        "connection_detection": {"correct": 0, "total": 0},
        "label_ocr": {"correct": 0, "total": 0},
    }

    for sample in dataset:
        result = await processbot_vision_pipeline(sample.image)

        # Compare predicted vs expected
        metrics["block_detection"]["total"] += len(sample.expected.blocks)
        metrics["block_type_matching"]["total"] += len(sample.expected.blocks)
        metrics["connection_detection"]["total"] += len(sample.expected.connections)
        metrics["label_ocr"]["total"] += len(sample.expected.blocks)

        for expected_block in sample.expected.blocks:
            matched = find_matching_block(result.blocks, expected_block)
            if matched:
                metrics["block_detection"]["correct"] += 1
                if matched.block_type == expected_block.block_type:
                    metrics["block_type_matching"]["correct"] += 1
                if matched.label == expected_block.label:
                    metrics["label_ocr"]["correct"] += 1

        for expected_conn in sample.expected.connections:
            if find_matching_connection(result.connections, expected_conn):
                metrics["connection_detection"]["correct"] += 1

    # Calculate percentages
    for key, counts in metrics.items():
        pct = (counts["correct"] / counts["total"] * 100) if counts["total"] > 0 else 0
        print(f"{key}: {pct:.1f}% ({counts['correct']}/{counts['total']})")

    # Assert minimum thresholds
    assert metrics["block_detection"]["correct"] / metrics["block_detection"]["total"] >= 0.85
    assert metrics["block_type_matching"]["correct"] / metrics["block_type_matching"]["total"] >= 0.80
    assert metrics["connection_detection"]["correct"] / metrics["connection_detection"]["total"] >= 0.80
    assert metrics["label_ocr"]["correct"] / metrics["label_ocr"]["total"] >= 0.70
```

### 4.3 Data Collection Plan

| Source | Quantity | Labeling | Timeline |
|--------|----------|----------|----------|
| Draw.io exports (clean) | 30 | Auto-label from .drawio XML | Day 1 |
| Whiteboard photos | 20 | Manual labeling (30 min each) | Week 1 |
| Paper napkin sketches | 20 | Manual labeling | Week 2 |
| Real MTK process diagrams | 10 | Denis labels (domain expert) | Week 2 |
| Public BPMN examples | 20 | Auto-label from BPMN XML | Day 1 |
| **Total baseline dataset** | **100** | | |

---

## Gap 5: COGS Analysis (Cost of Goods Sold)

### 5.1 Model Costs

| Model | Provider | Input $/1K tok | Output $/1K tok | Image $/img |
|-------|----------|---------------|-----------------|-------------|
| DeepSeek V4 Pro | RouterAI | $0.0014 | $0.0028 | $0.003 (vision) |
| GPT-4V (fallback) | OpenAI | $0.01 | $0.03 | $0.01 (vision) |
| Qwen 35B (local) | Self-hosted | $0.0004* | $0.0004* | N/A (text only) |

*Local model cost: electricity + GPU amortization ≈ $0.40/hour, ~10K tok/sec → $0.0004/1K tok

### 5.2 Per-Operation Cost

| Operation | Avg Input Tok | Avg Output Tok | Images | Model | COGS |
|-----------|--------------|----------------|--------|-------|------|
| Vision: clean diagram | 500 + 1 img | 3,000 | 1 | DeepSeek | $0.012 |
| Vision: poor quality | 800 + 1 img | 4,000 | 1 | DeepSeek | $0.016 |
| Vision: complex (50 blocks) | 1,200 + 1 img | 6,000 | 1 | DeepSeek | $0.022 |
| NLP: text→process | 2,000 | 3,500 | 0 | Qwen local | $0.002 |
| NLP: text→process | 2,000 | 3,500 | 0 | DeepSeek | $0.013 |
| Events: pattern mining | 5,000 | 2,000 | 0 | Qwen local | $0.003 |

### 5.3 Margin Analysis

| Plan | Price/mo | Generations | COGS/mo (avg) | Gross Margin |
|------|----------|-------------|---------------|--------------|
| Free | $0 | 0 | $0 | N/A |
| Pro | $9.90 | 10 vision + 20 text | $0.12 + $0.04 = $0.16 | **98.4%** |
| Enterprise | $29.90 | Unlimited (est. 50 vision + 100 text) | $0.60 + $0.20 = $0.80 | **97.3%** |

> **Conclusion:** With local model as default for text, margins are sustainable. Even all-cloud worst case: Pro margin drops to ~85% — still healthy. The business scales on volume.

### 5.4 Break-Even Analysis

```
Monthly fixed costs:
  Server (Hetzner AX102):     $85/mo
  DeepSeek API (base load):   $50/mo
  Domain/DNS:                 $15/mo
  Total:                      $150/mo

Break-even at:
  150 / 9.90 = ~16 Pro subscribers
  150 / 29.90 = ~5 Enterprise subscribers

With 10 Pro + 3 Enterprise = 10×9.90 + 3×29.90 = $99 + $89.70 = $188.70 → profitable at $38.70/mo
```

---

## Gap 6: Security Threat Model

### 6.1 Assets

| Asset | Sensitivity | Impact if Compromised |
|-------|-------------|----------------------|
| M2M JWT secret | HIGH | Attacker can deploy instances, read all tenant data |
| Tenant JWT secrets | HIGH | Attacker can impersonate any user |
| User PII (emails, names) | MEDIUM | GDPR/privacy violation |
| Process definitions | MEDIUM | Business logic exposure |
| Billing records | HIGH | Financial fraud possible |
| Uploaded images | LOW | Temporary, but may contain PII |

### 6.2 Threat Model (STRIDE)

| Threat | Vector | Severity | Mitigation |
|--------|--------|----------|------------|
| **Spoofing** | Stolen M2M JWT → deploy from fake Vela | 🔴 CRITICAL | JWT expires in 5min; jti nonce in Redis; IP whitelist for M2M |
| **Tampering** | Modified deploy manifest in transit | 🟡 MEDIUM | HTTPS everywhere; manifest hash verification |
| **Repudiation** | Deploy action denied by admin | 🟢 LOW | Audit logs with cryptographic chain |
| **Info Disclosure** | Vision images leaked from logs | 🟡 MEDIUM | Images discarded after processing; never logged |
| **Denial of Service** | 1000 deploy requests/sec | 🟡 MEDIUM | Rate limit: 10 deploys/min per source IP; M2M rate limit per service |
| **Elevation of Privilege** | Vela service account used to read tenant data | 🔴 CRITICAL | M2M scope restricted to `deploy:*` only; not `tenant:read` |

### 6.3 M2M Security Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  AETHER M2M AUTH GATEWAY                                        │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  JWT Validation                                          │ │
│  │  ├── Signature: HS256 (soon → RS256 for asymmetric)      │ │
│  │  ├── Expiry: 5 minutes                                   │ │
│  │  ├── Nonce (jti): checked against Redis (anti-replay)    │ │
│  │  └── IP binding: optional, configurable per service      │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Scope Enforcement                                        │ │
│  │  ┌──────────────┬────────────────────────────────────┐   │ │
│  │  │ Service      │ Allowed Scopes                      │   │ │
│  │  ├──────────────┼────────────────────────────────────┤   │ │
│  │  │ vela         │ deploy:write, deploy:read,         │   │ │
│  │  │              │ deploy:delete, processbot:generate  │   │ │
│  │  ├──────────────┼────────────────────────────────────┤   │ │
│  │  │ logicore     │ events:write, webhook:register     │   │ │
│  │  ├──────────────┼────────────────────────────────────┤   │ │
│  │  │ ai-ops       │ metrics:read, gpu:read, alerts:w   │   │ │
│  │  └──────────────┴────────────────────────────────────┘   │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Key Rotation                                             │ │
│  │  ├── Rotation interval: 30 days                           │ │
│  │  ├── Grace period: 24 hours (accept old+new)              │ │
│  │  ├── Announcement: X-Key-Version header                   │ │
│  │  └── Emergency rotation: manual trigger via admin API     │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 6.4 Image Security

```python
class ImageSecurityMiddleware:
    """Sanitize uploaded images before processing."""

    async def sanitize(self, image: bytes) -> SanitizedImage:
        # 1. Strip EXIF metadata (GPS, camera, timestamps)
        image = strip_exif(image)

        # 2. Detect and redact faces (privacy)
        face_regions = await detect_faces(image)
        image = redact_regions(image, face_regions)

        # 3. Scan for malicious content (ClamAV — optional)
        if settings.CLAMAV_ENABLED:
            scan_result = await clamav_scan(image)
            if scan_result.threats:
                raise MaliciousFileError(scan_result.threats)

        # 4. Blur PII-like text patterns in image
        # (passport numbers, phone numbers visible in photos)
        image = await blur_pii_in_image(image)

        return SanitizedImage(data=image, redacted_regions=len(face_regions))

    async def cleanup(self, image_id: str):
        """Delete image after processing. Images are NEVER stored."""
        await delete_image(image_id)
        logger.info(f"Image {image_id} purged after processing")
```

---

## Gap 7: OpenAPI Specification (Machine-Readable Contract)

### 7.1 Contract-First Approach

Instead of Markdown-only API docs, provide OpenAPI 3.1 YAML for:

- `POST /api/process-definitions/generate` (ProcessBot)
- `POST /api/v1/deploy` (Deploy Bridge)
- `GET /api/v1/deploy/status/{tenant_id}`
- `POST /api/v1/deploy/update/{tenant_id}`
- `DELETE /api/v1/deploy/{tenant_id}`

This enables:
- Auto-generated TypeScript client (Vela frontend → Aether backend)
- Auto-generated Pydantic models (from OpenAPI → Python validation)
- Contract testing (Dredd, Schemathesis)
- Documentation portal (Swagger UI, Scalar, Redoc)
