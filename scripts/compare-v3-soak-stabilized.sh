#!/usr/bin/env bash
set -euo pipefail

[ "$#" -eq 6 ] || {
  echo "usage: $0 REVISION_1 STABLE_1 REVISION_2 STABLE_2 REVISION_3 STABLE_3" >&2
  exit 2
}

property() {
  key=$1
  file=$2
  awk -F= -v wanted="$key" '$1 == wanted { sub(/^[^=]*=/, ""); print; found=1 } END { exit !found }' "$file"
}

declare -a runs cells starts
for index in "$@"; do
  run=$(realpath -e -- "$index")
  [ -d "$run/soak" ] || { echo "not a complete result directory: $index" >&2; exit 2; }
  for existing in "${runs[@]:-}"; do
    [ "$run" != "$existing" ] || { echo "duplicate comparison run: $run" >&2; exit 2; }
  done
  runs+=("$run")
done

environment_keys=(git_commit logical_cpus java_runtime jvm_options cloud_provider cloud_zone
  cloud_machine_type cloud_provisioning cloud_image_project cloud_image_family
  cloud_image cloud_image_id cloud_image_self_link cloud_image_created_at)
baseline_metadata=${runs[0]}/metadata.txt
for position in 0 1 2 3 4 5; do
  run=${runs[$position]}
  metadata="$run/metadata.txt"
  config="$run/soak/soak-config.properties"
  stabilization="$run/soak/soak-stabilization-analysis.properties"
  base="$run/soak/soak-analysis.properties"
  investigation="$run/soak/soak-investigation-analysis.properties"
  for file in "$metadata" "$config" "$stabilization" "$base" "$investigation" "$run/checksums.sha256"; do
    [ -s "$file" ] || { echo "missing comparison evidence: $file" >&2; exit 2; }
  done
  (cd "$run" && sha256sum -c checksums.sha256 >/dev/null) \
    || { echo "checksum validation failed: $run" >&2; exit 2; }
  [ "$(property stabilization_purpose "$config")" = screening ] \
    || { echo "comparison requires screening purpose" >&2; exit 2; }
  [ "$(property stabilization_status "$stabilization")" = READY ] \
    && [ "$(property measurement_started "$stabilization")" = true ] \
    && [ "$(property analysis_status "$base")" = VALID ] \
    && [ "$(property analysis_status "$investigation")" = VALID ] \
    || { echo "run is not valid READY evidence: $run" >&2; exit 2; }
  expected_cell=revision-update
  [ $((position % 2)) -eq 1 ] && expected_cell=stable-update
  actual_cell=$(property investigation_cell "$investigation")
  [ "$actual_cell" = "$expected_cell" ] \
    || { echo "unexpected cell at argument $((position + 1)): $actual_cell" >&2; exit 2; }
  cells[$position]=$actual_cell
  expected_update=revision
  expected_corpus_changed=true
  [ "$expected_cell" = stable-update ] \
    && expected_update=stable \
    && expected_corpus_changed=false
  for pair in documents:100000 readers:16 writers:1 seconds:600 \
    sample_seconds:1 top_k:10 corpus_profile:zipf-en-medium-4 \
    index_cycles:false per_query_metrics:true stabilization_seconds:300 \
    stabilization_window_seconds:60 allow_reduced_stabilization_test:false \
    jfr_output:none "update_mode:$expected_update"; do
    key=${pair%%:*}; expected=${pair#*:}
    [ "$(property "$key" "$config")" = "$expected" ] \
      || { echo "frozen screening configuration mismatch for $key" >&2; exit 2; }
  done
  [ "$(property summary_corpus_changed "$investigation")" = \
      "$expected_corpus_changed" ] \
    || { echo "cell identity behavior mismatch" >&2; exit 2; }
  awk '/^working_tree_begin$/ { begin=NR } /^working_tree_end$/ { end=NR } END { exit !(begin && end == begin + 1) }' \
    "$metadata" || { echo "comparison run has a dirty working tree" >&2; exit 2; }
  starts[$position]=$(property started_utc "$metadata")
  for key in "${environment_keys[@]}"; do
    expected=$(property "$key" "$baseline_metadata")
    actual=$(property "$key" "$metadata")
    [ "$actual" = "$expected" ] \
      || { echo "frozen environment mismatch for $key" >&2; exit 2; }
  done
done

[ "$(property cloud_zone "$baseline_metadata")" = us-west4-a ] \
  && [ "$(property cloud_machine_type "$baseline_metadata")" = c3d-standard-30 ] \
  && [ "$(property cloud_provisioning "$baseline_metadata")" = standard ] \
  && [ "$(property cloud_image "$baseline_metadata")" = \
      ubuntu-2404-noble-amd64-v20260826 ] \
  && [ "$(property jvm_options "$baseline_metadata")" = '-Xms8g -Xmx16g' ] \
  || { echo "screening environment does not match the frozen cloud cell" >&2; exit 2; }

# Frozen chronological order: S1,R1,R2,S2,S3,R3.
chronological=(1 0 2 3 5 4)
previous=
for position in "${chronological[@]}"; do
  current=${starts[$position]}
  if [ -n "$previous" ] && [[ ! "$current" > "$previous" ]]; then
    echo "runs do not follow the frozen alternating chronological order" >&2
    exit 2
  fi
  previous=$current
done

data=$(mktemp "${TMPDIR:-/tmp}/gse-stabilized-compare.XXXXXX")
trap 'rm -f -- "$data"' EXIT
metrics=(aggregate text bool phrase fuzzy)
for metric in "${metrics[@]}"; do
  for round in 0 1 2; do
    revision=${runs[$((round * 2))]}
    stable=${runs[$((round * 2 + 1))]}
    if [ "$metric" = aggregate ]; then
      drift_key=read_rate_drift_pct
      rate_key=summary_read_ops_per_second
      revision_drift_file="$revision/soak/soak-analysis.properties"
      stable_drift_file="$stable/soak/soak-analysis.properties"
      revision_rate_file=$revision_drift_file
      stable_rate_file=$stable_drift_file
    else
      drift_key=${metric}_read_rate_drift_pct
      rate_key=summary_${metric}_read_ops_per_second
      revision_drift_file="$revision/soak/soak-investigation-analysis.properties"
      stable_drift_file="$stable/soak/soak-investigation-analysis.properties"
      revision_rate_file=$revision_drift_file
      stable_rate_file=$stable_drift_file
    fi
    printf '%s %d %s %s %s %s\n' \
      "$metric" "$((round + 1))" \
      "$(property "$drift_key" "$revision_drift_file")" \
      "$(property "$drift_key" "$stable_drift_file")" \
      "$(property "$rate_key" "$revision_rate_file")" \
      "$(property "$rate_key" "$stable_rate_file")" >> "$data"
  done
done

awk '
BEGIN { print "comparison_version=1"; print "comparison_status=VALID"; overall=1; aggregate_direction=0; query_same=0 }
{
  for (field=3; field<=6; field++) if ($field !~ /^-?[0-9]+([.][0-9]+)?$/) { invalid=1; exit 2 }
  if ($5 <= 0 || $6 <= 0) { invalid=1; exit 2 }
  metric=$1; round=$2; rd[metric,round]=$3; sd[metric,round]=$4; rr[metric,round]=$5; sr[metric,round]=$6; seen[metric]=1
}
END {
  if (invalid) exit 2
  split("aggregate text bool phrase fuzzy", order, " ")
  for (m=1; m<=5; m++) {
    metric=order[m]; sumrd=sumSd=sumrr=sumsr=0
    driftDirection=0; rateDirection=0; driftPairs=1; ratePairs=1
    for (round=1; round<=3; round++) {
      sumrd+=rd[metric,round]; sumSd+=sd[metric,round]; sumrr+=rr[metric,round]; sumsr+=sr[metric,round]
      dd=rd[metric,round]-sd[metric,round]; dr=rr[metric,round]-sr[metric,round]
      print metric "_round_" round "_revision_drift_pct=" rd[metric,round]
      print metric "_round_" round "_stable_drift_pct=" sd[metric,round]
      print metric "_round_" round "_revision_rate=" rr[metric,round]
      print metric "_round_" round "_stable_rate=" sr[metric,round]
      direction=(dd>0)-(dd<0); rateDir=(dr>0)-(dr<0)
      if (direction==0 || (driftDirection!=0 && direction!=driftDirection)) driftPairs=0; if (driftDirection==0) driftDirection=direction
      if (rateDir==0 || (rateDirection!=0 && rateDir!=rateDirection)) ratePairs=0; if (rateDirection==0) rateDirection=rateDir
    }
    meanrd=sumrd/3; meansd=sumSd/3; meanrr=sumrr/3; meansr=sumsr/3
    sdrd=sd3(rd[metric,1],rd[metric,2],rd[metric,3],meanrd); sdsd=sd3(sd[metric,1],sd[metric,2],sd[metric,3],meansd)
    sdrr=sd3(rr[metric,1],rr[metric,2],rr[metric,3],meanrr); sdsr=sd3(sr[metric,1],sr[metric,2],sr[metric,3],meansr)
    driftGap=abs(meanrd-meansd); rateGap=abs(meanrr-meansr)
    driftVariabilityThreshold=2*max(sdrd,sdsd); rateMinimumEffect=0.03*meansr; rateVariabilityThreshold=2*max(sdrr,sdsr)
    directionAgrees=(rateDirection==driftDirection)
    driftGate=driftPairs && driftGap>=3.0 && driftGap>=driftVariabilityThreshold
    rateGate=ratePairs && rateGap>=rateMinimumEffect && rateGap>=rateVariabilityThreshold && directionAgrees
    joint=driftGate && rateGate
    print metric "_revision_drift_mean_pct=" meanrd; print metric "_stable_drift_mean_pct=" meansd
    print metric "_revision_drift_sample_sd=" sdrd; print metric "_stable_drift_sample_sd=" sdsd
    print metric "_drift_contrast_abs_pct=" driftGap; print metric "_drift_min_effect_pct=3"
    print metric "_drift_variability_threshold=" driftVariabilityThreshold
    print metric "_drift_paired_direction_consistent=" bool(driftPairs); print metric "_drift_gate=" bool(driftGate)
    print metric "_revision_rate_mean=" meanrr; print metric "_stable_rate_mean=" meansr
    print metric "_revision_rate_sample_sd=" sdrr; print metric "_stable_rate_sample_sd=" sdsr
    print metric "_rate_contrast_abs=" rateGap; print metric "_rate_min_effect=" rateMinimumEffect
    print metric "_rate_variability_threshold=" rateVariabilityThreshold
    print metric "_rate_paired_direction_consistent=" bool(ratePairs)
    print metric "_rate_drift_direction_agrees=" bool(directionAgrees); print metric "_rate_gate=" bool(rateGate)
    print metric "_direction=" driftDirection; print metric "_joint_supported=" bool(joint)
    if (metric=="aggregate") { overall=joint; aggregate_direction=driftDirection }
    else if (joint && driftDirection==aggregate_direction) query_same=1
  }
  print "differentiating_factor_supported=" bool(overall && query_same)
}
function abs(value) { return value < 0 ? -value : value }
function max(a,b) { return a > b ? a : b }
function sd3(a,b,c,mean) { return sqrt(((a-mean)^2+(b-mean)^2+(c-mean)^2)/2) }
function bool(value) { return value ? "true" : "false" }
' "$data"
