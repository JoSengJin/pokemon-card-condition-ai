import argparse
import json
import pickle
import sys
from pathlib import Path
from .data import load_manifest, prepare, training_readiness
from .model import Analyzer, evaluate, train


def main():
    parser = argparse.ArgumentParser(description="Experimental card-condition model; local only")
    commands = parser.add_subparsers(dest="command", required=True)
    from .regions import GLARE_AREAS, REGION_LABELS
    visibility = commands.add_parser('visibility-experiment')
    visibility.add_argument('manifest')
    visibility.add_argument('output')
    visibility.add_argument('--backbone', choices=('mobilenet_v3_small','dinov2_vits14'), default='mobilenet_v3_small')
    visibility.add_argument('--side-aware', action='store_true', help='Train separate front/back centroids; unchanged MobileNet context only')
    visibility.add_argument('--standardize', action='store_true', help='Train-only group-balanced feature scaling; requires --local-signals --centroid')
    visibility.add_argument('--local-signals', action='store_true', help='Fixed 3x3 color/texture descriptor; MobileNet centroid only')
    visibility.add_argument('--epochs', type=int, default=20)
    visibility.add_argument('--tiles', action='store_true')
    visibility.add_argument('--interior', action='store_true', help='Diagnostic central90% crop; discards outer edges')
    visibility.add_argument('--centroid', action='store_true', help='Train-only weighted nearest-centroid baseline; no epoch selection')
    heldout = commands.add_parser('visibility-heldout')
    heldout.add_argument('checkpoint')
    heldout.add_argument('manifest')
    heldout.add_argument('output')
    heldout.add_argument('--expected-model-sha256', required=True)
    heldout.add_argument('--device', choices=('auto','cpu','mps'), default='auto')
    heldout.add_argument('--test-seal')
    heldout.add_argument('--test-seal-sha256')
    heldout.add_argument('--test-candidate')
    heldout.add_argument('--test-candidate-sha256')
    crossfit = commands.add_parser('visibility-crossfit')
    crossfit.add_argument('manifest')
    crossfit.add_argument('output')
    crossfit.add_argument('--compare-context', action='store_true', help='Fixed crop plus source context comparison on train-only folds')
    crossfit.add_argument('--compare-glare-only', action='store_true', help='Glare versus explicitly clear subset; other restrictions unknown')
    crossfit.add_argument('--compare-logistic', action='store_true', help='Fixed lambda=1 BCE side classifier on identical train-only folds')
    crossfit.add_argument('--compare-ridge', action='store_true', help='Fixed lambda=1 side ridge comparison on identical train-only folds')
    crossfit.add_argument('--device', choices=('auto','cpu','mps'), default='auto')
    audit = commands.add_parser('visibility-input-audit')
    audit.add_argument('manifest')
    audit.add_argument('output')
    geometry = commands.add_parser('visibility-geometry-review')
    geometry.add_argument('manifest')
    geometry.add_argument('output')
    visibility_compare = commands.add_parser('visibility-compare')
    visibility_compare.add_argument('reference')
    visibility_compare.add_argument('candidate')
    visibility.add_argument('--device', choices=('auto', 'cpu', 'mps'), default='auto')
    visibility_predict = commands.add_parser('visibility-predict')
    visibility_predict.add_argument('checkpoint')
    visibility_predict.add_argument('image')
    visibility_predict.add_argument('--side', choices=('front','back'), help='Required for side-aware checkpoints')
    visibility_predict.add_argument('--box', type=float, nargs=4, required=True)
    visibility_predict.add_argument('--device', choices=('auto', 'cpu', 'mps'), default='auto')
    listing = commands.add_parser('listing-infer')
    listing.add_argument('manifest')
    listing.add_argument('checkpoint')
    listing.add_argument('output')
    listing.add_argument('--profile-memory', action='store_true', help='Sample MPS region backbone allocations; not true peak memory')
    listing.add_argument('--batch-views', action='store_true', help='Experimental inference-only batching of fixed views')
    listing.add_argument('--observation-checkpoint', help='Optional frozen observation model; evidence only, no routing changes')
    listing.add_argument('--device', choices=('auto', 'cpu', 'mps'), default='auto')
    listing_predict = commands.add_parser('listing-predict')
    listing_predict.add_argument('checkpoint', nargs='?', help='Direct checkpoint; omit when --release is used')
    listing_predict.add_argument('request', help='JSON with id and optional front/back photo inputs; no labels or split')
    listing_predict.add_argument('--release', help='Pinned release manifest; verifies package version and checkpoint SHA256 before inference')
    listing_predict.add_argument('--batch-views', action='store_true')
    listing_predict.add_argument('--recall-checkpoint', help='Optional additional defect review model; no final verdict')
    listing_predict.add_argument('--observation-checkpoint', help='Optional face-level evidence; no routing changes')
    listing_predict.add_argument('--device', choices=('auto', 'cpu', 'mps'), default='auto')
    listing_predict.add_argument('--usage-log', help='Append one JSON usage record per request (timings, outcome, hold counts, release); a record that cannot be written fails the request')
    pilot_summary = commands.add_parser('pilot-summary', help='Measured F2 pilot conditions from a usage log; never certifies a pilot')
    pilot_summary.add_argument('log')
    pilot_summary.add_argument('--reviews', nargs='*', default=[], help='listing-review-record files linked by exact report SHA')
    listing_review = commands.add_parser('listing-review', help='Static page to review one listing-predict result')
    listing_review.add_argument('report', help='listing-predict JSON output')
    listing_review.add_argument('request', help='The same request JSON given to listing-predict')
    listing_review.add_argument('--output', required=True)
    review_record = commands.add_parser('listing-review-record', help='Validate exported review decisions; never a label')
    review_record.add_argument('report')
    review_record.add_argument('decisions')
    review_record.add_argument('--output', required=True)
    input_check = commands.add_parser('input-review')
    input_check.add_argument('manifest')
    input_check.add_argument('output')
    input_check.add_argument('--card', action='append', required=True)
    point_bench = commands.add_parser('point-benchmark')
    point_bench.add_argument('manifest')
    point_bench.add_argument('checkpoint')
    point_bench.add_argument('output')
    point_bench.add_argument('--device', choices=('auto', 'cpu', 'mps'), default='auto')
    probe = commands.add_parser('point-probe')
    probe.add_argument('manifest')
    probe.add_argument('output')
    probe.add_argument('checkpoints', nargs='+')
    probe.add_argument('--card', action='append', required=True)
    probe.add_argument('--history', action='append', required=True)
    point_compare = commands.add_parser('point-compare')
    point_compare.add_argument('manifest')
    point_compare.add_argument('output')
    point_compare.add_argument('reports', nargs='+')
    point_compare.add_argument('--reference', action='append', default=[])
    point_run = commands.add_parser('point-experiment')
    point_run.add_argument('manifest')
    point_run.add_argument('output')
    point_run.add_argument('--epochs',type=int,default=5)
    point_run.add_argument('--backbone',choices=('mobilenet_v3_small','resnet18'),default='mobilenet_v3_small')
    point_run.add_argument('--image-size',type=int,choices=(224,448),default=224)
    point_run.add_argument('--balanced-selection',action='store_true',help='Experimental equal class then group validation BCE; training unchanged')
    point_run.add_argument('--fine-tune-spatial',action='store_true',help='Train the last spatial MobileNet block, context or fixed tiles')
    point_run.add_argument('--balance',action='store_true',help='Train-only class mass balance after physical-group weights')
    point_run.add_argument('--side-balance',action='store_true',help='Experimental train-only equal front/back and normal/defect mass; requires --balance')
    point_run.add_argument('--standardize-features',action='store_true',help='Experimental train-only feature scaling folded into the frozen edge head')
    point_run.add_argument('--nonlinear-head',action='store_true',help='Experimental 8-unit tanh edge head; frozen backbone and original features')
    point_run.add_argument('--focal-loss',action='store_true',help='Experimental train-only gamma=2 focal loss; validation selection remains BCE')
    point_run.add_argument('--zero-init-head',action='store_true',help='Initialize frozen surface-only linear head at zero; existing default unchanged')
    point_run.add_argument('--surface-input',choices=('context','tiles'),help='Separate surface-only context or fixed 2x2 tiles experiment')
    point_run.add_argument('--edge-input',choices=('context','views','tiles','tiles-max'),help='Experimental edge-only head: full patch or full patch plus outer-edge views or fixed 2x2 tiles (tiles-max uses spatial max pooling)')
    point_run.add_argument('--device',choices=('auto','cpu','mps'),default='auto')
    crops = commands.add_parser("point-dataset")
    crops.add_argument("manifest")
    crops.add_argument("output")
    points = commands.add_parser("point-audit")
    points.add_argument("manifest")
    points.add_argument("output")
    region_eval = commands.add_parser("region-evaluate")
    region_eval.add_argument("manifest")
    region_eval.add_argument("checkpoint")
    region_eval.add_argument("output")
    region_eval.add_argument("--history", action="append", required=True)
    region_eval.add_argument("--device", choices=("auto", "cpu", "mps"), default="auto")
    region_eval.add_argument('--test-seal')
    region_eval.add_argument('--test-seal-sha256')
    region_eval.add_argument('--test-candidate')
    region_eval.add_argument('--test-candidate-sha256')
    region_predict = commands.add_parser("region-predict")
    region_predict.add_argument("checkpoint")
    region_predict.add_argument("image")
    region_predict.add_argument("--card-box", type=float, nargs=4, required=True)
    region_predict.add_argument("--area", choices=GLARE_AREAS, required=True)
    region_predict.add_argument("--unknown", choices=REGION_LABELS, nargs="*", default=[])
    region_predict.add_argument("--batch-views", action="store_true")
    region_predict.add_argument("--device", choices=("auto", "cpu", "mps"), default="auto")
    patch = commands.add_parser("region-experiment")
    patch.add_argument("manifest")
    patch.add_argument("output")
    patch.add_argument("--epochs", type=int, default=5)
    patch.add_argument("--group-balance", action="store_true")
    patch.add_argument("--backbone", choices=("mobilenet_v3_small", "resnet18"), default="mobilenet_v3_small")
    patch.add_argument("--device", choices=("auto", "cpu", "mps"), default="auto")
    coverage = commands.add_parser("data-coverage")
    coverage.add_argument("manifest")
    coverage.add_argument("output")
    region = commands.add_parser("region-audit")
    region.add_argument("manifest")
    region.add_argument("output")
    region_compare = commands.add_parser("region-compare")
    region_compare.add_argument("manifest")
    region_compare.add_argument("output")
    region_compare.add_argument("reports", nargs="+")
    region_compare.add_argument("--reference", action="append", default=[])
    plan = commands.add_parser("region-review-plan")
    plan.add_argument("manifest")
    plan.add_argument("checkpoint")
    plan.add_argument("output")
    plan.add_argument("--skip-card", action="append", default=[], help="Do not request another label from this card or physical group")
    plan.add_argument("--device", choices=("auto", "cpu", "mps"), default="auto")
    audit = commands.add_parser("label-audit")
    audit.add_argument("inventory")
    audit.add_argument("reference")
    audit.add_argument("output")
    errors = commands.add_parser("error-review")
    errors.add_argument("manifest")
    errors.add_argument("report")
    errors.add_argument("output")
    resliced = commands.add_parser("reslice-visibility")
    resliced.add_argument("reference")
    resliced.add_argument("updated")
    resliced.add_argument("report")
    resliced.add_argument("checkpoint")
    resliced.add_argument("output")
    route = commands.add_parser("routing-audit")
    route.add_argument("manifest")
    route.add_argument("report")
    route.add_argument("output")
    compare = commands.add_parser("compare-validation")
    compare.add_argument("manifest")
    compare.add_argument("output")
    compare.add_argument("reports", nargs="+")
    bench = commands.add_parser("benchmark-validation")
    bench.add_argument("manifest")
    bench.add_argument("checkpoint")
    bench.add_argument("output")
    bench.add_argument("--device", choices=("auto", "cpu", "mps"), default="auto")
    side = commands.add_parser("side-experiment")
    side.add_argument("manifest")
    side.add_argument("output")
    views = side.add_mutually_exclusive_group()
    views.add_argument("--crop", action="store_true")
    views.add_argument("--tiles", action="store_true")
    side.add_argument("--balance", action="store_true", help="Train-only class weights; validation loss remains unweighted")
    side.add_argument("--fine-tune-last", action="store_true", help="Train only MobileNet's final feature block and the head")
    side.add_argument("--backbone", choices=("mobilenet_v3_small", "resnet18"), default="mobilenet_v3_small")
    side.add_argument("--epochs", type=int, default=5)
    side.add_argument("--device", choices=("auto", "cpu", "mps"), default="auto")
    side_predict = commands.add_parser("side-predict")
    side_predict.add_argument("checkpoint")
    side_predict.add_argument("--front")
    side_predict.add_argument("--back")
    side_predict.add_argument("--front-box", type=float, nargs=4)
    side_predict.add_argument("--back-box", type=float, nargs=4)
    side_predict.add_argument("--device", choices=("auto", "cpu", "mps"), default="auto")
    side_eval = commands.add_parser("side-evaluate")
    side_eval.add_argument("manifest")
    side_eval.add_argument("checkpoint")
    side_eval.add_argument("output")
    side_eval.add_argument("--kind", choices=("regression", "final"), required=True)
    side_eval.add_argument("--history", action="append", default=[], help="Prior development manifest; repeat for all historical datasets")
    side_eval.add_argument("--device", choices=("auto", "cpu", "mps"), default="auto")
    side_eval.add_argument('--test-seal')
    side_eval.add_argument('--test-seal-sha256')
    side_eval.add_argument('--test-candidate')
    side_eval.add_argument('--test-candidate-sha256')
    snap = commands.add_parser("snapshot")
    snap.add_argument("inventory")
    snap.add_argument("output")
    snap.add_argument("--reference", required=True)
    snap.add_argument("--unassigned", choices=("train", "val", "test"))
    review = commands.add_parser("review")
    review.add_argument("inventory")
    review.add_argument("--port", type=int, default=8766)
    check = commands.add_parser("check")
    check.add_argument("manifest")
    inventory = commands.add_parser("prepare")
    inventory.add_argument("folder")
    inventory.add_argument("output")
    validate = commands.add_parser("validate")
    validate.add_argument("manifest")
    training = commands.add_parser("train")
    training.add_argument("manifest")
    training.add_argument("checkpoint")
    training.add_argument("--image-size", type=int, choices=(224, 448), default=224)
    training.add_argument("--epochs", type=int, default=5)
    training.add_argument("--batch-size", type=int, default=4)
    training.add_argument("--scratch-smoke", action="store_true", help="Random weights for plumbing tests only")
    scoring = commands.add_parser("evaluate")
    scoring.add_argument("manifest")
    scoring.add_argument("checkpoint")
    scoring.add_argument("--threshold", type=float, default=0.9)
    prediction = commands.add_parser("predict")
    prediction.add_argument("checkpoint")
    prediction.add_argument("front")
    prediction.add_argument("--back")
    for command in (training, scoring, prediction):
        command.add_argument("--device", choices=("auto", "cpu", "mps"), default="auto")
    args = parser.parse_args()
    try:
        if args.command == 'visibility-experiment':
            from .visibility_model import experiment
            result = experiment(args.manifest, args.output, args.epochs, args.device, tiles=args.tiles, centroid=args.centroid, interior=args.interior, backbone_name=args.backbone, local_signals=args.local_signals, standardize=args.standardize, side_aware=args.side_aware)
        elif args.command == 'visibility-heldout':
            from .observation_heldout import evaluate_heldout
            result = evaluate_heldout(args.checkpoint,args.manifest,args.output,args.expected_model_sha256,args.device, test_seal=args.test_seal, test_seal_sha256=args.test_seal_sha256, test_candidate=args.test_candidate, test_candidate_sha256=args.test_candidate_sha256)
        elif args.command == 'visibility-crossfit':
            from .observation_crossfit import group_crossfit
            result = group_crossfit(args.manifest,args.output,args.device,compare_ridge=args.compare_ridge, compare_context=args.compare_context, compare_logistic=args.compare_logistic, compare_glare_only=args.compare_glare_only)
        elif args.command == 'visibility-input-audit':
            from .observation_audit import audit_inputs
            result = audit_inputs(args.manifest,args.output)
        elif args.command == 'visibility-geometry-review':
            from .geometry_review import prepare_geometry_review
            result = prepare_geometry_review(args.manifest,args.output)
        elif args.command == 'visibility-compare':
            from .visibility_compare import compare_reports
            result = compare_reports(json.loads(Path(args.reference).read_text()), json.loads(Path(args.candidate).read_text()))
        elif args.command == 'visibility-predict':
            from .visibility_model import VisibilityAnalyzer
            result = VisibilityAnalyzer(args.checkpoint, args.device).analyze(args.image, args.box, side=args.side)
        elif args.command == 'listing-infer':
            from .listing_inference import infer_listings
            result = infer_listings(args.manifest, args.checkpoint, args.output, args.device, args.observation_checkpoint, args.batch_views, args.profile_memory)
        elif args.command == 'listing-predict':
            from .listing_model import ListingAnalyzer
            from .pilot_record import UsageRecorder
            usage = UsageRecorder(args.usage_log, args.release)
            try:
                request = json.loads(Path(args.request).read_text())
                usage.start(request)
                if (args.checkpoint is None) == (args.release is None):
                    raise ValueError('listing-predict requires exactly one of CHECKPOINT or --release')
                analyzer = ListingAnalyzer(args.checkpoint, args.device, observation_checkpoint=args.observation_checkpoint, recall_checkpoint=args.recall_checkpoint, release=args.release)
                usage.loaded()
                result = analyzer.analyze(request, batch_views=args.batch_views)
                usage.finish(result)
            except Exception as exc:
                usage.fail(exc)
                raise
        elif args.command == 'pilot-summary':
            from .pilot_summary import summarize
            result = summarize(args.log, args.reviews)
        elif args.command == 'listing-review':
            from .listing_review import review_page
            result = review_page(args.report, args.request, args.output)
        elif args.command == 'listing-review-record':
            from .listing_review import review_record
            result = review_record(args.report, args.decisions, args.output)
        elif args.command == 'input-review':
            from .input_review import input_review
            result = input_review(args.manifest, args.output, args.card)
        elif args.command == 'point-benchmark':
            from .point_benchmark import benchmark_points
            result = benchmark_points(args.manifest, args.checkpoint, args.output, args.device)
        elif args.command == 'point-probe':
            from .point_probe import point_probe
            result = point_probe(args.manifest, args.checkpoints, args.output, args.card, args.history)
        elif args.command == 'point-compare':
            from .comparison import compare_regions
            result = compare_regions(args.manifest, args.reports, args.output, args.reference, point_grid=True)
        elif args.command == 'point-experiment':
            from .region_experiment import experiment
            result = experiment(args.manifest,args.output,epochs=args.epochs,device=args.device,point_grid=True,balance=args.balance,backbone_name=args.backbone,edge_input=args.edge_input,image_size=args.image_size,fine_tune_spatial=args.fine_tune_spatial,balanced_selection=args.balanced_selection,side_balance=args.side_balance,standardize_features=args.standardize_features,nonlinear_head=args.nonlinear_head,focal_loss=args.focal_loss,surface_input=args.surface_input,zero_init_head=args.zero_init_head)
        elif args.command == "point-dataset":
            from .point_dataset import point_dataset
            result = point_dataset(args.manifest, args.output)
        elif args.command == "point-audit":
            from .point_audit import point_audit
            result = point_audit(args.manifest, args.output)
        elif args.command == "region-evaluate":
            from .region_evaluation import evaluate_regions
            result = evaluate_regions(args.manifest, args.checkpoint, args.output, args.history, args.device, test_seal=args.test_seal, test_seal_sha256=args.test_seal_sha256, test_candidate=args.test_candidate, test_candidate_sha256=args.test_candidate_sha256)
        elif args.command == "region-predict":
            from .region_model import RegionAnalyzer
            result = RegionAnalyzer(args.checkpoint, args.device).analyze(args.image, args.card_box, args.area, args.unknown, args.batch_views)
        elif args.command == "region-experiment":
            from .region_experiment import experiment
            result = experiment(args.manifest, args.output, epochs=args.epochs, device=args.device,
                                group_balance=args.group_balance, backbone_name=args.backbone)
        elif args.command == "data-coverage":
            from .data_coverage import data_coverage
            result = data_coverage(args.manifest, args.output)
        elif args.command == "region-audit":
            from .region_dataset import region_audit
            result = region_audit(args.manifest, args.output)
        elif args.command == "region-compare":
            from .comparison import compare_regions
            result = compare_regions(args.manifest, args.reports, args.output, args.reference)
        elif args.command == "region-review-plan":
            from .region_review_plan import review_plan
            result = review_plan(args.manifest, args.checkpoint, args.output, args.device, args.skip_card)
        elif args.command == "label-audit":
            from .label_audit import label_audit
            result = label_audit(args.inventory, args.reference, args.output)
        elif args.command == "error-review":
            from .error_review import error_review
            result = error_review(args.manifest, args.report, args.output)
        elif args.command == "reslice-visibility":
            from .reslice import reslice
            result = reslice(args.reference, args.updated, args.report, args.checkpoint, args.output)
        elif args.command == "routing-audit":
            from .routing_audit import routing_audit
            result = routing_audit(args.manifest, args.report, args.output)
        elif args.command == "compare-validation":
            from .comparison import compare_validation
            result = compare_validation(args.manifest, args.reports, args.output)
        elif args.command == "benchmark-validation":
            from .benchmark import benchmark_validation
            result = benchmark_validation(args.manifest, args.checkpoint, args.output, args.device)
        elif args.command == "side-experiment":
            from .side_experiment import experiment
            result = experiment(args.manifest, args.output, args.crop, args.device, args.epochs, tiles=args.tiles, balance=args.balance, fine_tune_last=args.fine_tune_last, backbone_name=args.backbone)
        elif args.command == "side-predict":
            from .side_model import SideAnalyzer
            result = SideAnalyzer(args.checkpoint, args.device).analyze(args.front, args.back, args.front_box, args.back_box)
        elif args.command == "side-evaluate":
            from .side_evaluation import evaluate_sides
            result = evaluate_sides(args.manifest, args.checkpoint, args.output, args.kind, args.history, args.device, test_seal=args.test_seal, test_seal_sha256=args.test_seal_sha256, test_candidate=args.test_candidate, test_candidate_sha256=args.test_candidate_sha256)
        elif args.command == "snapshot":
            from .snapshot import snapshot
            result = snapshot(args.inventory, args.output, args.reference, args.unassigned)
        elif args.command == "review":
            from .review import serve
            serve(args.inventory, args.port)
            return
        elif args.command == "check":
            result = training_readiness(load_manifest(args.manifest))
        elif args.command == "prepare":
            result = prepare(args.folder, args.output)
        elif args.command == "validate":
            rows = load_manifest(args.manifest)
            result = {"records": len(rows), "splits": {s: sum(r["split"] == s for r in rows)
                                                       for s in ("train", "val", "test")}}
        elif args.command == "train":
            result = train(args.manifest, args.checkpoint, args.epochs, args.batch_size,
                           args.device, pretrained=not args.scratch_smoke, image_size=args.image_size)
        elif args.command == "evaluate":
            result = evaluate(args.manifest, args.checkpoint, args.threshold, args.device)
        else:
            result = Analyzer(args.checkpoint, args.device).analyze(args.front, args.back)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except (ValueError, OSError, RuntimeError, pickle.UnpicklingError, EOFError) as exc:
        message = ("Invalid or incomplete checkpoint; use Gemini fallback"
                   if isinstance(exc, (pickle.UnpicklingError, EOFError)) else str(exc))
        print(json.dumps({"error": message, "requires_gemini": True}), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
