#include "VoiceForgeLookup.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

USoundWave* UVoiceForgeLookup::FindDialogue(const FString& CharacterId,const FString& DialogueId,FString& Subtitle)
{
    Subtitle.Empty();
    static TArray<TSharedPtr<FJsonValue>> Rows;
    if (Rows.IsEmpty()) {
        FString Text;
        if (!FFileHelper::LoadFileToString(Text, *(FPaths::ProjectContentDir()/TEXT("VoiceForge/dialogue_manifest.json")))) return nullptr;
        auto Reader=TJsonReaderFactory<>::Create(Text);
        if (!FJsonSerializer::Deserialize(Reader, Rows)) return nullptr;
    }
    for (const auto& Value : Rows) {
        auto Row=Value->AsObject();
        if (!Row.IsValid()) continue;
        if (Row->GetStringField(TEXT("character_id"))==CharacterId && Row->GetStringField(TEXT("dialogue_id"))==DialogueId) {
            Subtitle=Row->GetStringField(TEXT("subtitle"));
            return LoadObject<USoundWave>(nullptr,*Row->GetStringField(TEXT("asset_path")));
        }
    }
    return nullptr;
}
