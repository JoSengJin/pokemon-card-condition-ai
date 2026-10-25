"""Deduplicate source hashes already present in the review evidence registry."""


def compact_manifest(manifest, evidence):
    by_source = {(entry['path'], entry['sha256']): key for key, entry in evidence.items()
                 if isinstance(entry, dict) and 'path' in entry and 'sha256' in entry}
    return [{'evidence_id': by_source[(item['path'], item['sha256'])]}
            if (item['path'], item['sha256']) in by_source else item for item in manifest]


def expand_manifest(packet):
    result = []
    for item in packet.get('latest_sources', []):
        if 'evidence_id' in item:
            if set(item) != {'evidence_id'}:
                raise ValueError('Invalid source reference')
            source = packet['evidence'][item['evidence_id']]
            result.append({'path': source['path'], 'sha256': source['sha256']})
        else:
            result.append(item)
    return result
