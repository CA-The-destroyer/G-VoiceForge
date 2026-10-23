#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Sound/SoundWave.h"
#include "VoiceForgeLookup.generated.h"

// Add Json, JsonUtilities to your module Build.cs dependencies.
UCLASS()
class UVoiceForgeLookup : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    // Loads exported cooked SoundWaves; no editor modules or Python at runtime.
    UFUNCTION(BlueprintCallable, Category="VoiceForge")
    static USoundWave* FindDialogue(const FString& CharacterId, const FString& DialogueId, FString& Subtitle);
};
