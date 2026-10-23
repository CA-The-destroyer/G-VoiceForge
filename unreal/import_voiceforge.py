"""Run in Unreal Editor with the Python Editor Script Plugin enabled.

Set VOICEFORGE_EXPORT to an extracted export folder, or place this script in it.
The editor importer is never used by packaged game runtime code.
"""
import csv
import json
import os
from pathlib import Path
import unreal

ROOT=Path(os.environ.get('VOICEFORGE_EXPORT',str(Path(__file__).resolve().parent)))
rows=json.loads((ROOT/'Metadata'/'dialogue.json').read_text(encoding='utf-8'))
cache_file=ROOT/'Metadata'/'imported_hashes.json'
cache=json.loads(cache_file.read_text()) if cache_file.exists() else {}
failures=[]
manifest=[]
for row in rows:
    asset=row['asset_path']
    try:
        exists=unreal.EditorAssetLibrary.does_asset_exist(asset)
        current_hash=cache.get(asset)
        if exists:
            existing=unreal.load_asset(asset)
            current_hash=unreal.EditorAssetLibrary.get_metadata_tag(existing,'VoiceForge.AudioHash') or current_hash
        if current_hash!=row['audio_hash'] or not exists:
            task=unreal.AssetImportTask()
            task.set_editor_property('filename',str(ROOT/row['audio']))
            task.set_editor_property('destination_path',asset.rsplit('/',1)[0])
            task.set_editor_property('destination_name',asset.rsplit('/',1)[1])
            task.set_editor_property('automated',True)
            task.set_editor_property('replace_existing',True)
            task.set_editor_property('save',True)
            unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
            if not task.get_editor_property('imported_object_paths'): raise RuntimeError('No imported asset path returned.')
            sound=unreal.load_asset(asset)
            unreal.EditorAssetLibrary.set_metadata_tag(sound,'VoiceForge.CharacterId',row['character_id'])
            unreal.EditorAssetLibrary.set_metadata_tag(sound,'VoiceForge.DialogueId',row['dialogue_id'])
            unreal.EditorAssetLibrary.set_metadata_tag(sound,'VoiceForge.Subtitle',row['subtitle'])
            unreal.EditorAssetLibrary.set_metadata_tag(sound,'VoiceForge.AudioHash',row['audio_hash'])
            unreal.EditorAssetLibrary.save_loaded_asset(sound)
            cache[asset]=row['audio_hash']
        # FSoftObjectPath requires package.asset notation for runtime JSON loading.
        row=dict(row,asset_path=asset+'.'+asset.rsplit('/',1)[-1])
        manifest.append(row)
    except Exception as exc:
        failures.append({'dialogue_id':row['dialogue_id'],'error':str(exc)})
        unreal.log_error('VoiceForge '+row['dialogue_id']+': '+str(exc))
cache_file.write_text(json.dumps(cache,indent=2))
content=Path(unreal.Paths.project_content_dir())/'VoiceForge'
content.mkdir(exist_ok=True)
(content/'dialogue_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(ROOT/'Metadata'/'import_failures.json').write_text(json.dumps(failures,indent=2))
unreal.log(f'VoiceForge imported/skipped {len(manifest)} lines; {len(failures)} failures. Manifest: {content}')
