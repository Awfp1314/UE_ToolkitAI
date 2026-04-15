#include "PropertySerializer.h"
#include "Authoring/AuthoringHelpers.h"

#include "Components/Widget.h"
#include "GameplayTagContainer.h"
#include "JsonObjectConverter.h"
#include "UObject/UnrealType.h"

#include <initializer_list>

namespace PropertySerializerInternal
{
	static bool IsInstancedObjectProperty(const FObjectPropertyBase* ObjectProperty);
	static TSharedPtr<FJsonObject> BuildInlineObjectJson(const UObject* Object);
}

TSharedPtr<FJsonValue> FPropertySerializer::SerializePropertyValue(const FProperty* Property, const void* ValuePtr)
{
	if (!Property || !ValuePtr)
	{
		return nullptr;
	}

	if (const FBoolProperty* BoolProp = CastField<FBoolProperty>(Property))
	{
		return MakeShared<FJsonValueBoolean>(BoolProp->GetPropertyValue(ValuePtr));
	}

	if (const FEnumProperty* EnumProp = CastField<FEnumProperty>(Property))
	{
		if (const UEnum* Enum = EnumProp->GetEnum())
		{
			const FNumericProperty* UnderlyingProp = EnumProp->GetUnderlyingProperty();
			const int64 EnumValue = UnderlyingProp->GetSignedIntPropertyValue(ValuePtr);
			return MakeShared<FJsonValueString>(Enum->GetNameStringByValue(EnumValue));
		}
	}

	if (const FByteProperty* ByteProp = CastField<FByteProperty>(Property))
	{
		if (ByteProp->Enum)
		{
			const int64 EnumValue = static_cast<int64>(ByteProp->GetPropertyValue(ValuePtr));
			return MakeShared<FJsonValueString>(ByteProp->Enum->GetNameStringByValue(EnumValue));
		}

		return MakeShared<FJsonValueNumber>(ByteProp->GetPropertyValue(ValuePtr));
	}

	if (const FInt8Property* Int8Prop = CastField<FInt8Property>(Property))
	{
		return MakeShared<FJsonValueNumber>(Int8Prop->GetPropertyValue(ValuePtr));
	}

	if (const FInt16Property* Int16Prop = CastField<FInt16Property>(Property))
	{
		return MakeShared<FJsonValueNumber>(Int16Prop->GetPropertyValue(ValuePtr));
	}

	if (const FIntProperty* IntProp = CastField<FIntProperty>(Property))
	{
		return MakeShared<FJsonValueNumber>(IntProp->GetPropertyValue(ValuePtr));
	}

	if (const FInt64Property* Int64Prop = CastField<FInt64Property>(Property))
	{
		return MakeShared<FJsonValueNumber>(static_cast<double>(Int64Prop->GetPropertyValue(ValuePtr)));
	}

	if (const FUInt16Property* UInt16Prop = CastField<FUInt16Property>(Property))
	{
		return MakeShared<FJsonValueNumber>(UInt16Prop->GetPropertyValue(ValuePtr));
	}

	if (const FUInt32Property* UInt32Prop = CastField<FUInt32Property>(Property))
	{
		return MakeShared<FJsonValueNumber>(UInt32Prop->GetPropertyValue(ValuePtr));
	}

	if (const FUInt64Property* UInt64Prop = CastField<FUInt64Property>(Property))
	{
		return MakeShared<FJsonValueNumber>(static_cast<double>(UInt64Prop->GetPropertyValue(ValuePtr)));
	}

	if (const FFloatProperty* FloatProp = CastField<FFloatProperty>(Property))
	{
		return MakeShared<FJsonValueNumber>(FloatProp->GetPropertyValue(ValuePtr));
	}

	if (const FDoubleProperty* DoubleProp = CastField<FDoubleProperty>(Property))
	{
		return MakeShared<FJsonValueNumber>(DoubleProp->GetPropertyValue(ValuePtr));
	}

	if (const FNumericProperty* NumericProp = CastField<FNumericProperty>(Property))
	{
		if (NumericProp->IsFloatingPoint())
		{
			return MakeShared<FJsonValueNumber>(NumericProp->GetFloatingPointPropertyValue(ValuePtr));
		}
	}

	if (const FStrProperty* StrProp = CastField<FStrProperty>(Property))
	{
		return MakeShared<FJsonValueString>(StrProp->GetPropertyValue(ValuePtr));
	}

	if (const FNameProperty* NameProp = CastField<FNameProperty>(Property))
	{
		return MakeShared<FJsonValueString>(NameProp->GetPropertyValue(ValuePtr).ToString());
	}

	if (const FTextProperty* TextProp = CastField<FTextProperty>(Property))
	{
		return MakeShared<FJsonValueString>(TextProp->GetPropertyValue(ValuePtr).ToString());
	}

	if (const FArrayProperty* ArrayProp = CastField<FArrayProperty>(Property))
	{
		TArray<TSharedPtr<FJsonValue>> JsonArray;
		FScriptArrayHelper ArrayHelper(ArrayProp, ValuePtr);

		for (int32 Index = 0; Index < ArrayHelper.Num(); ++Index)
		{
			const TSharedPtr<FJsonValue> ElementValue =
				SerializePropertyValue(ArrayProp->Inner, ArrayHelper.GetRawPtr(Index));
			JsonArray.Add(ElementValue ? ElementValue : MakeShared<FJsonValueNull>());
		}

		return MakeShared<FJsonValueArray>(JsonArray);
	}

	if (const FSetProperty* SetProp = CastField<FSetProperty>(Property))
	{
		TArray<TSharedPtr<FJsonValue>> JsonArray;
		FScriptSetHelper SetHelper(SetProp, ValuePtr);

		for (int32 Index = 0; Index < SetHelper.Num(); ++Index)
		{
			if (!SetHelper.IsValidIndex(Index))
			{
				continue;
			}

			const TSharedPtr<FJsonValue> ElementValue =
				SerializePropertyValue(SetProp->ElementProp, SetHelper.GetElementPtr(Index));
			JsonArray.Add(ElementValue ? ElementValue : MakeShared<FJsonValueNull>());
		}

		return MakeShared<FJsonValueArray>(JsonArray);
	}

	if (const FMapProperty* MapProp = CastField<FMapProperty>(Property))
	{
		TSharedPtr<FJsonObject> JsonMap = MakeShared<FJsonObject>();
		FScriptMapHelper MapHelper(MapProp, ValuePtr);

		for (int32 Index = 0; Index < MapHelper.Num(); ++Index)
		{
			if (!MapHelper.IsValidIndex(Index))
			{
				continue;
			}

			FString KeyStr;
			MapProp->KeyProp->ExportText_Direct(KeyStr, MapHelper.GetKeyPtr(Index), nullptr, nullptr, PPF_None);
			const TSharedPtr<FJsonValue> ValueJson =
				SerializePropertyValue(MapProp->ValueProp, MapHelper.GetValuePtr(Index));
			JsonMap->SetField(KeyStr, ValueJson ? ValueJson : MakeShared<FJsonValueNull>());
		}

		return MakeShared<FJsonValueObject>(JsonMap);
	}

	if (const FStructProperty* StructProp = CastField<FStructProperty>(Property))
	{
		if (const UScriptStruct* ScriptStruct = StructProp->Struct)
		{
			TSharedPtr<FJsonObject> JsonObj = MakeShared<FJsonObject>();
			if (FJsonObjectConverter::UStructToJsonObject(ScriptStruct, ValuePtr, JsonObj.ToSharedRef(), 0, 0))
			{
				return MakeShared<FJsonValueObject>(JsonObj);
			}
		}
	}

	if (CastField<FSoftClassProperty>(Property))
	{
		const FSoftObjectPtr& SoftPtr = *static_cast<const FSoftObjectPtr*>(ValuePtr);
		return MakeShared<FJsonValueString>(SoftPtr.ToSoftObjectPath().ToString());
	}

	if (CastField<FSoftObjectProperty>(Property))
	{
		const FSoftObjectPtr& SoftPtr = *static_cast<const FSoftObjectPtr*>(ValuePtr);
		return MakeShared<FJsonValueString>(SoftPtr.ToSoftObjectPath().ToString());
	}

	if (const FObjectPropertyBase* ObjProp = CastField<FObjectPropertyBase>(Property))
	{
		if (const UObject* ReferencedObject = ObjProp->GetObjectPropertyValue(ValuePtr))
		{
			if (PropertySerializerInternal::IsInstancedObjectProperty(ObjProp))
			{
				return MakeShared<FJsonValueObject>(
					PropertySerializerInternal::BuildInlineObjectJson(ReferencedObject).ToSharedRef());
			}

			return MakeShared<FJsonValueString>(ReferencedObject->GetPathName());
		}

		return MakeShared<FJsonValueNull>();
	}

	FString ValueStr;
	Property->ExportText_Direct(ValueStr, ValuePtr, nullptr, nullptr, PPF_None);
	return MakeShared<FJsonValueString>(ValueStr);
}

TSharedPtr<FJsonObject> FPropertySerializer::SerializePropertyOverrides(const UObject* Object)
{
	return SerializePropertyOverridesAgainstBaseline(
		Object,
		Object ? Object->GetClass()->GetDefaultObject() : nullptr);
}

TSharedPtr<FJsonObject> FPropertySerializer::SerializePropertyOverridesAgainstBaseline(
	const UObject* Object,
	const UObject* BaselineObject)
{
	TSharedPtr<FJsonObject> Overrides = MakeShared<FJsonObject>();

	if (!Object)
	{
		return Overrides;
	}

	const UClass* ObjectClass = Object->GetClass();
	if (!BaselineObject)
	{
		BaselineObject = ObjectClass->GetDefaultObject();
	}

	for (TFieldIterator<FProperty> PropIt(ObjectClass); PropIt; ++PropIt)
	{
		const FProperty* Property = *PropIt;

		if (Object->IsA<UWidget>() && Property->GetFName() == GET_MEMBER_NAME_CHECKED(UWidget, Slot))
		{
			continue;
		}

		if (!Property->HasAnyPropertyFlags(CPF_Edit | CPF_BlueprintVisible))
		{
			continue;
		}

		if (Property->HasAnyPropertyFlags(CPF_Deprecated | CPF_Transient))
		{
			continue;
		}

		const bool bHasMatchingBaselineClass = BaselineObject
			&& BaselineObject->GetClass()->IsChildOf(Property->GetOwnerClass());
		if (bHasMatchingBaselineClass && Property->Identical_InContainer(Object, BaselineObject))
		{
			continue;
		}

		const void* ValuePtr = Property->ContainerPtrToValuePtr<void>(Object);
		const TSharedPtr<FJsonValue> JsonValue = SerializePropertyValue(Property, ValuePtr);
		if (JsonValue)
		{
			Overrides->SetField(Property->GetName(), JsonValue);
		}
	}

	return Overrides;
}

TArray<TSharedPtr<FJsonValue>> FPropertySerializer::SerializeUserProperties(
	const void* Container,
	const UClass* ContainerClass,
	const TArray<const UClass*>& SkipClasses)
{
	TArray<TSharedPtr<FJsonValue>> Properties;

	if (!Container || !ContainerClass)
	{
		return Properties;
	}

	for (TFieldIterator<FProperty> PropIt(ContainerClass); PropIt; ++PropIt)
	{
		FProperty* Property = *PropIt;
		const UClass* OwnerClass = Property->GetOwnerClass();

		if (OwnerClass && SkipClasses.Contains(OwnerClass))
		{
			continue;
		}

		if (Property->HasAnyPropertyFlags(CPF_Deprecated | CPF_Transient))
		{
			continue;
		}

		TSharedPtr<FJsonObject> PropObj = MakeShared<FJsonObject>();
		PropObj->SetStringField(TEXT("name"), Property->GetName());
		PropObj->SetStringField(TEXT("cppType"), Property->GetCPPType());

		const void* ValuePtr = Property->ContainerPtrToValuePtr<void>(Container);
		const TSharedPtr<FJsonValue> TypedValue = SerializePropertyValue(Property, ValuePtr);
		if (TypedValue)
		{
			PropObj->SetField(TEXT("value"), TypedValue);
		}

		if (const FObjectPropertyBase* ObjProp = CastField<FObjectPropertyBase>(Property))
		{
			if (const UObject* ReferencedObj = ObjProp->GetObjectPropertyValue(ValuePtr))
			{
				PropObj->SetStringField(TEXT("referencePath"), ReferencedObj->GetPathName());
			}
		}

		Properties.Add(MakeShared<FJsonValueObject>(PropObj));
	}

	return Properties;
}

namespace PropertySerializerInternal
{

static bool IsInstancedObjectProperty(const FObjectPropertyBase* ObjectProperty)
{
	return ObjectProperty && ObjectProperty->HasAnyPropertyFlags(
		CPF_InstancedReference | CPF_ContainsInstancedReference | CPF_ExportObject | CPF_PersistentInstance);
}

static void AddError(TArray<FString>& OutErrors, const FString& Message);

/**
 * Extracts a tag name string from the UE text-export format (TagName="Foo.Bar")
 * that ExportText_InContainer / ExportTextItem produces for FGameplayTag.
 * Returns true if a tag name was successfully parsed (even if empty).
 */
static bool TryParseGameplayTagExportText(const FString& ExportText, FString& OutTagName)
{
	OutTagName.Reset();

	FString Trimmed = ExportText.TrimStartAndEnd();
	if (Trimmed.IsEmpty())
	{
		return true;
	}

	// Plain tag name without parentheses (e.g. "Foo.Bar")
	if (!Trimmed.StartsWith(TEXT("(")))
	{
		OutTagName = Trimmed;
		return true;
	}

	// Struct export format: (TagName="Foo.Bar") or ()
	if (Trimmed == TEXT("()"))
	{
		return true;
	}

	// Try to extract TagName="..." from the parenthesised form
	static const FString TagNamePrefix = TEXT("TagName=");

	int32 TagNameStart = Trimmed.Find(TagNamePrefix, ESearchCase::IgnoreCase, ESearchDir::FromStart, 1);
	if (TagNameStart == INDEX_NONE)
	{
		return false;
	}

	int32 ValueStart = TagNameStart + TagNamePrefix.Len();
	if (ValueStart >= Trimmed.Len())
	{
		return false;
	}

	// Value may be quoted ("Foo.Bar") or unquoted (Foo.Bar)
	FString ValuePortion = Trimmed.Mid(ValueStart);
	// Strip trailing ')' and whitespace
	ValuePortion.TrimEndInline();
	if (ValuePortion.EndsWith(TEXT(")")))
	{
		ValuePortion.LeftChopInline(1);
	}

	// Strip surrounding quotes if present
	if (ValuePortion.Len() >= 2
		&& ValuePortion[0] == TEXT('"')
		&& ValuePortion[ValuePortion.Len() - 1] == TEXT('"'))
	{
		ValuePortion = ValuePortion.Mid(1, ValuePortion.Len() - 2);
	}

	// "None" is UE's FName representation of NAME_None
	if (ValuePortion == TEXT("None") || ValuePortion.IsEmpty())
	{
		return true;
	}

	OutTagName = ValuePortion;
	return true;
}

/**
 * Attempts to apply a JSON value to an FGameplayTag property.
 * Accepts:
 *   - JSON string: "(TagName=\"Foo.Bar\")" (UE export text)
 *   - JSON string: "Foo.Bar" (plain tag name)
 *   - JSON object: { "TagName": "Foo.Bar" }
 * Returns true if the value was handled (even if the tag is invalid/empty).
 * Returns false if the JSON value format is unrecognised.
 */
static bool TryApplyGameplayTagValue(const FStructProperty* StructProp,
                                     void* ValuePtr,
                                     const TSharedPtr<FJsonValue>& JsonValue,
                                     TArray<FString>& OutErrors,
                                     const bool bValidationOnly)
{
	if (!StructProp || !StructProp->Struct || StructProp->Struct != FGameplayTag::StaticStruct())
	{
		return false;
	}

	FString TagName;

	// Try JSON object format: { "TagName": "Foo.Bar" }
	// IMPORTANT: Check Type before calling AsObject(). UE's FJsonValueString::AsObject()
	// returns a non-null TSharedPtr wrapping an empty FJsonObject instead of nullptr,
	// which would cause the if-branch to be taken and TagName to remain empty.
	if (JsonValue->Type == EJson::Object)
	{
		const TSharedPtr<FJsonObject> JsonObject = JsonValue->AsObject();
		if (JsonObject.IsValid())
		{
			JsonObject->TryGetStringField(TEXT("TagName"), TagName);
		}
	}
	else
	{
		// Try string format: "(TagName=\"Foo.Bar\")" or "Foo.Bar"
		FString StringValue;
		if (!JsonValue->TryGetString(StringValue))
		{
			AddError(OutErrors, FString::Printf(
				TEXT("Property '%s': FGameplayTag expects a string (tag name or export text) or object ({\"TagName\":\"...\"}), got %s"),
				*StructProp->GetName(),
				*FString::Printf(TEXT("JSON type %d"), static_cast<int32>(JsonValue->Type))));
			return true; // handled (with error)
		}

		if (!TryParseGameplayTagExportText(StringValue, TagName))
		{
			// Not a recognised format — fall through to generic struct import
			return false;
		}
	}

	// Empty tag name → clear the tag
	if (TagName.IsEmpty())
	{
		if (!bValidationOnly)
		{
			FGameplayTag* Tag = static_cast<FGameplayTag*>(ValuePtr);
			*Tag = FGameplayTag();
		}
		return true;
	}

	// Request the tag through the gameplay tag manager so it is properly validated
	const FGameplayTag ResolvedTag = FGameplayTag::RequestGameplayTag(FName(*TagName), /*bErrorIfNotFound=*/ false);
	if (!ResolvedTag.IsValid())
	{
		AddError(OutErrors, FString::Printf(
			TEXT("Property '%s': gameplay tag '%s' is not registered. "
			     "Register it in the project's GameplayTags settings or DefaultGameplayTags.ini before setting it."),
			*StructProp->GetName(),
			*TagName));
		return true; // handled (with error)
	}

	if (!bValidationOnly)
	{
		FGameplayTag* Tag = static_cast<FGameplayTag*>(ValuePtr);
		*Tag = ResolvedTag;
	}

	return true;
}

static TSharedPtr<FJsonObject> CloneJsonObjectWithoutInlineMetadata(const TSharedPtr<FJsonObject>& Source)
{
	if (!Source.IsValid())
	{
		return MakeShared<FJsonObject>();
	}

	const TArray<FString> SkippedKeys = {
		TEXT("class"),
		TEXT("classPath"),
		TEXT("objectClass"),
		TEXT("objectClassPath"),
		TEXT("objectPath"),
		TEXT("objectName"),
		TEXT("name"),
		TEXT("properties")
	};

	TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Source->Values)
	{
		if (SkippedKeys.Contains(Pair.Key))
		{
			continue;
		}

		Result->SetField(Pair.Key, Pair.Value);
	}

	return Result;
}

static TSharedPtr<FJsonObject> BuildInlineObjectJson(const UObject* Object)
{
	if (!Object)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> JsonObject = MakeShared<FJsonObject>();
	JsonObject->SetStringField(TEXT("classPath"), Object->GetClass()->GetPathName());
	JsonObject->SetStringField(TEXT("objectName"), Object->GetName());
	JsonObject->SetObjectField(
		TEXT("properties"),
		FPropertySerializer::SerializePropertyOverridesAgainstBaseline(
			Object,
			Object->GetClass()->GetDefaultObject()));
	return JsonObject;
}

static bool ParseInlineObjectClassPath(const TSharedPtr<FJsonObject>& JsonObject, FString& OutClassPath)
{
	if (!JsonObject.IsValid())
	{
		return false;
	}

	return JsonObject->TryGetStringField(TEXT("classPath"), OutClassPath)
		|| JsonObject->TryGetStringField(TEXT("class"), OutClassPath)
		|| JsonObject->TryGetStringField(TEXT("objectClassPath"), OutClassPath)
		|| JsonObject->TryGetStringField(TEXT("objectClass"), OutClassPath);
}

static TSharedPtr<FJsonObject> GetInlineObjectProperties(const TSharedPtr<FJsonObject>& JsonObject)
{
	if (!JsonObject.IsValid())
	{
		return nullptr;
	}

	const TSharedPtr<FJsonObject>* NestedProperties = nullptr;
	if (JsonObject->TryGetObjectField(TEXT("properties"), NestedProperties)
		&& NestedProperties
		&& NestedProperties->IsValid())
	{
		return *NestedProperties;
	}

	return CloneJsonObjectWithoutInlineMetadata(JsonObject);
}

static void AddError(TArray<FString>& OutErrors, const FString& Message)
{
	OutErrors.Add(Message);
}

static FProperty* FindPropertyOnClassHierarchy(const UClass* TargetClass, const FName PropertyName)
{
	if (!TargetClass || PropertyName.IsNone())
	{
		return nullptr;
	}

	FProperty* Property = TargetClass->FindPropertyByName(PropertyName);
	if (Property)
	{
		return Property;
	}

	for (const UClass* SuperClass = TargetClass->GetSuperClass();
	     SuperClass && !Property;
	     SuperClass = SuperClass->GetSuperClass())
	{
		Property = SuperClass->FindPropertyByName(PropertyName);
	}

	return Property;
}

static FString DescribeResolvedClass(const UClass* TargetClass)
{
	if (!TargetClass)
	{
		return TEXT("<null>");
	}

	FString Description = TargetClass->GetName();
	for (const UClass* SuperClass = TargetClass->GetSuperClass();
	     SuperClass;
	     SuperClass = SuperClass->GetSuperClass())
	{
		if (SuperClass->HasAnyClassFlags(CLASS_Native))
		{
			if (SuperClass != TargetClass)
			{
				Description += FString::Printf(TEXT(" (native parent: %s)"), *SuperClass->GetName());
			}
			break;
		}
	}

	return Description;
}

static bool ClassHierarchyContainsName(const UClass* TargetClass, const FString& ClassName)
{
	for (const UClass* CurrentClass = TargetClass; CurrentClass; CurrentClass = CurrentClass->GetSuperClass())
	{
		if (CurrentClass->GetName().Equals(ClassName, ESearchCase::IgnoreCase))
		{
			return true;
		}
	}

	return false;
}

static TArray<FString> TokenizeIdentifier(const FString& Identifier)
{
	TArray<FString> Tokens;
	FString CurrentToken;

	for (int32 Index = 0; Index < Identifier.Len(); ++Index)
	{
		const TCHAR Char = Identifier[Index];
		if (Char == TEXT('_') || Char == TEXT('-') || Char == TEXT(' ') || Char == TEXT('/'))
		{
			if (!CurrentToken.IsEmpty())
			{
				Tokens.Add(CurrentToken.ToLower());
				CurrentToken.Reset();
			}
			continue;
		}

		const bool bStartNewToken = CurrentToken.Len() > 0
			&& FChar::IsUpper(Char)
			&& !FChar::IsUpper(CurrentToken[CurrentToken.Len() - 1]);
		if (bStartNewToken)
		{
			Tokens.Add(CurrentToken.ToLower());
			CurrentToken.Reset();
		}

		CurrentToken.AppendChar(Char);
	}

	if (!CurrentToken.IsEmpty())
	{
		Tokens.Add(CurrentToken.ToLower());
	}

	return Tokens;
}

static int32 ScorePropertySuggestion(const FString& RequestedProperty, const FString& CandidateProperty)
{
	if (CandidateProperty.IsEmpty())
	{
		return 0;
	}

	const FString RequestedLower = RequestedProperty.ToLower();
	const FString CandidateLower = CandidateProperty.ToLower();

	int32 Score = 0;
	if (CandidateLower == RequestedLower)
	{
		return 1000;
	}
	if (CandidateLower.Contains(RequestedLower) || RequestedLower.Contains(CandidateLower))
	{
		Score += 120;
	}
	if (CandidateLower.StartsWith(RequestedLower.Left(FMath::Min(3, RequestedLower.Len()))))
	{
		Score += 40;
	}

	const TArray<FString> RequestedTokens = TokenizeIdentifier(RequestedProperty);
	const TArray<FString> CandidateTokens = TokenizeIdentifier(CandidateProperty);
	for (const FString& RequestedToken : RequestedTokens)
	{
		if (RequestedToken.Len() < 3)
		{
			continue;
		}

		for (const FString& CandidateToken : CandidateTokens)
		{
			if (CandidateToken == RequestedToken)
			{
				Score += 50;
			}
			else if (CandidateToken.Contains(RequestedToken) || RequestedToken.Contains(CandidateToken))
			{
				Score += 20;
			}
		}
	}

	return Score;
}

static TArray<FString> FindEditablePropertySuggestions(const UClass* TargetClass,
                                                       const FString& RequestedProperty,
                                                       const int32 MaxSuggestions = 5)
{
	if (!TargetClass)
	{
		return {};
	}

	TArray<TPair<FString, int32>> RankedCandidates;
	TSet<FString> SeenProperties;

	for (TFieldIterator<FProperty> PropIt(TargetClass); PropIt; ++PropIt)
	{
		const FProperty* Property = *PropIt;
		if (!Property
			|| !Property->HasAnyPropertyFlags(CPF_Edit | CPF_BlueprintVisible)
			|| Property->HasAnyPropertyFlags(CPF_Deprecated | CPF_Transient))
		{
			continue;
		}

		const FString PropertyName = Property->GetName();
		if (SeenProperties.Contains(PropertyName))
		{
			continue;
		}
		SeenProperties.Add(PropertyName);

		const int32 Score = ScorePropertySuggestion(RequestedProperty, PropertyName);
		if (Score > 0)
		{
			RankedCandidates.Add(TPair<FString, int32>(PropertyName, Score));
		}
	}

	RankedCandidates.Sort([](const TPair<FString, int32>& Left, const TPair<FString, int32>& Right)
	{
		if (Left.Value == Right.Value)
		{
			return Left.Key < Right.Key;
		}
		return Right.Value < Left.Value;
	});

	TArray<FString> Suggestions;
	for (const TPair<FString, int32>& Candidate : RankedCandidates)
	{
		Suggestions.Add(Candidate.Key);
		if (Suggestions.Num() >= MaxSuggestions)
		{
			break;
		}
	}

	return Suggestions;
}

static bool IsCommonUIButtonWrapperPropertyGap(const UClass* TargetClass, const FString& RequestedProperty)
{
	if (!ClassHierarchyContainsName(TargetClass, TEXT("CommonButtonBase")))
	{
		return false;
	}

	for (const FString& KnownGap : {TEXT("BackgroundColor"), TEXT("WidgetStyle"), TEXT("ColorAndOpacity")})
	{
		if (RequestedProperty.Equals(KnownGap, ESearchCase::IgnoreCase))
		{
			return true;
		}
	}

	return false;
}

static FString BuildPropertyNotFoundMessage(const UClass* TargetClass, const FString& RequestedProperty)
{
	FString Message = FString::Printf(
		TEXT("Property '%s' not found on resolved class '%s'"),
		*RequestedProperty,
		*DescribeResolvedClass(TargetClass));

	if (IsCommonUIButtonWrapperPropertyGap(TargetClass, RequestedProperty))
	{
		Message += TEXT(". CommonUI unsupported surface: UCommonButtonBase exposes a wrapper widget, not raw UButton background/style fields. Use extract_commonui_button_style, create_commonui_button_style, modify_commonui_button_style, or apply_commonui_button_style instead.");
	}

	const TArray<FString> Suggestions = FindEditablePropertySuggestions(TargetClass, RequestedProperty);
	if (Suggestions.Num() > 0)
	{
		Message += FString::Printf(TEXT(". Closest editable properties: %s"), *FString::Join(Suggestions, TEXT(", ")));
	}

	return Message;
}

static void MaybeEnableOverrideFlag(UObject* Target,
                                    const TSharedPtr<FJsonObject>& PropertiesJson,
                                    const FProperty* Property,
                                    const bool bValidationOnly)
{
	if (!Target || !Property || !PropertiesJson.IsValid())
	{
		return;
	}

	const FString PropertyName = Property->GetName();
	if (PropertyName.StartsWith(TEXT("bOverride_")))
	{
		return;
	}

	const FString OverridePropertyName = FString::Printf(TEXT("bOverride_%s"), *PropertyName);
	if (PropertiesJson->HasField(OverridePropertyName))
	{
		return;
	}

	FProperty* OverrideProperty = FindPropertyOnClassHierarchy(Target->GetClass(), FName(*OverridePropertyName));
	FBoolProperty* OverrideBoolProperty = CastField<FBoolProperty>(OverrideProperty);
	if (!OverrideBoolProperty
		|| !OverrideBoolProperty->HasAnyPropertyFlags(CPF_Edit | CPF_BlueprintVisible))
	{
		return;
	}

	if (!bValidationOnly)
	{
		void* OverrideValuePtr = OverrideBoolProperty->ContainerPtrToValuePtr<void>(Target);
		OverrideBoolProperty->SetPropertyValue(OverrideValuePtr, true);
	}
}

struct FTemporaryPropertyStorage
{
	const FProperty* Property = nullptr;
	void* Data = nullptr;

	explicit FTemporaryPropertyStorage(const FProperty* InProperty)
		: Property(InProperty)
	{
		if (Property)
		{
			Data = FMemory::Malloc(Property->GetSize(), Property->GetMinAlignment());
			Property->InitializeValue(Data);
		}
	}

	~FTemporaryPropertyStorage()
	{
		if (Property && Data)
		{
			Property->DestroyValue(Data);
			FMemory::Free(Data);
		}
	}
};

static bool ApplyJsonValueToPropertyInternal(const FProperty* Property,
                                             void* ValuePtr,
                                             UObject* OwnerObject,
                                             const TSharedPtr<FJsonValue>& JsonValue,
                                             TArray<FString>& OutErrors,
                                             bool bValidationOnly);

static bool ApplyObjectReference(const FObjectPropertyBase* ObjectProperty,
                                 void* ValuePtr,
                                 UObject* OwnerObject,
                                 const TSharedPtr<FJsonValue>& JsonValue,
                                 TArray<FString>& OutErrors,
                                 bool bValidationOnly)
{
	if (!JsonValue.IsValid())
	{
		ObjectProperty->SetObjectPropertyValue(ValuePtr, nullptr);
		return true;
	}

	if (JsonValue->Type == EJson::Null)
	{
		if (!bValidationOnly)
		{
			ObjectProperty->SetObjectPropertyValue(ValuePtr, nullptr);
		}
		return true;
	}

	const TSharedPtr<FJsonObject> JsonObject = JsonValue->Type == EJson::Object
		? JsonValue->AsObject()
		: nullptr;
	if (JsonObject.IsValid())
	{
		if (!IsInstancedObjectProperty(ObjectProperty))
		{
			AddError(OutErrors, FString::Printf(
				TEXT("Property '%s': expected string asset path for non-instanced object reference"),
				*ObjectProperty->GetName()));
			return false;
		}

		FString ClassPath;
		UClass* ResolvedClass = ObjectProperty->PropertyClass;
		if (ParseInlineObjectClassPath(JsonObject, ClassPath) && !ClassPath.IsEmpty())
		{
			ResolvedClass = FAuthoringHelpers::ResolveClass(ClassPath, ObjectProperty->PropertyClass);
			if (!ResolvedClass)
			{
				AddError(OutErrors, FString::Printf(TEXT("Property '%s': failed to load inline object class '%s'"),
					*ObjectProperty->GetName(), *ClassPath));
				return false;
			}
			if (!ResolvedClass->IsChildOf(ObjectProperty->PropertyClass))
			{
				AddError(OutErrors, FString::Printf(TEXT("Property '%s': inline object class '%s' is not compatible with '%s'"),
					*ObjectProperty->GetName(), *ResolvedClass->GetPathName(), *ObjectProperty->PropertyClass->GetPathName()));
				return false;
			}
		}

		UObject* ExistingObject = ObjectProperty->GetObjectPropertyValue(ValuePtr);
		if (ExistingObject && ExistingObject->GetClass() != ResolvedClass)
		{
			AddError(OutErrors, FString::Printf(TEXT("Property '%s': inline object class changes are not supported; clear the property before assigning '%s'"),
				*ObjectProperty->GetName(), *ResolvedClass->GetPathName()));
			return false;
		}

		UObject* WorkingObject = ExistingObject;
		if (bValidationOnly)
		{
			if (ExistingObject)
			{
				WorkingObject = DuplicateObject<UObject>(ExistingObject, GetTransientPackage());
			}
			else
			{
				WorkingObject = NewObject<UObject>(GetTransientPackage(), ResolvedClass);
			}
		}
		else if (!ExistingObject)
		{
			WorkingObject = NewObject<UObject>(
				OwnerObject ? OwnerObject : GetTransientPackage(),
				ResolvedClass,
				ObjectProperty->GetFName(),
				RF_Transactional);
		}

		if (!WorkingObject)
		{
			AddError(OutErrors, FString::Printf(TEXT("Property '%s': failed to create inline object instance"),
				*ObjectProperty->GetName()));
			return false;
		}

		const TSharedPtr<FJsonObject> PropertiesJson = GetInlineObjectProperties(JsonObject);
		TArray<FString> NestedErrors;
		const bool bNestedSuccess = FPropertySerializer::ApplyPropertiesFromJson(
			WorkingObject,
			PropertiesJson,
			NestedErrors,
			bValidationOnly,
			true);
		OutErrors.Append(NestedErrors);
		if (!bNestedSuccess)
		{
			return false;
		}

		if (!bValidationOnly)
		{
			ObjectProperty->SetObjectPropertyValue(ValuePtr, WorkingObject);
		}

		return true;
	}

	FString PathValue;
	if (!JsonValue->TryGetString(PathValue))
	{
		AddError(OutErrors, FString::Printf(TEXT("Property '%s': expected string asset path"), *ObjectProperty->GetName()));
		return false;
	}

	if (PathValue.IsEmpty())
	{
		if (!bValidationOnly)
		{
			ObjectProperty->SetObjectPropertyValue(ValuePtr, nullptr);
		}
		return true;
	}

	UObject* LoadedObject = FAuthoringHelpers::ResolveObject(PathValue, ObjectProperty->PropertyClass);
	if (!LoadedObject)
	{
		AddError(OutErrors, FString::Printf(TEXT("Property '%s': failed to load object '%s'"),
			*ObjectProperty->GetName(), *PathValue));
		return false;
	}

	if (!bValidationOnly)
	{
		ObjectProperty->SetObjectPropertyValue(ValuePtr, LoadedObject);
	}

	return true;
}

static bool ApplyJsonValueToPropertyInternal(const FProperty* Property,
                                             void* ValuePtr,
                                             UObject* OwnerObject,
                                             const TSharedPtr<FJsonValue>& JsonValue,
                                             TArray<FString>& OutErrors,
                                             const bool bValidationOnly)
{
	if (!Property)
	{
		return false;
	}

	if (!JsonValue.IsValid())
	{
		AddError(OutErrors, FString::Printf(TEXT("Property '%s': JSON value is null"), *Property->GetName()));
		return false;
	}

	void* WorkingPtr = ValuePtr;
	TUniquePtr<FTemporaryPropertyStorage> TempStorage;
	if (bValidationOnly)
	{
		TempStorage = MakeUnique<FTemporaryPropertyStorage>(Property);
		if (ValuePtr)
		{
			Property->CopyCompleteValue(TempStorage->Data, ValuePtr);
		}
		WorkingPtr = TempStorage->Data;
	}

	if (const FBoolProperty* BoolProp = CastField<FBoolProperty>(Property))
	{
		bool bValue = false;
		if (!JsonValue->TryGetBool(bValue))
		{
			AddError(OutErrors, FString::Printf(TEXT("Property '%s': expected bool value"), *Property->GetName()));
			return false;
		}
		if (!bValidationOnly)
		{
			BoolProp->SetPropertyValue(WorkingPtr, bValue);
		}
		return true;
	}

	if (const FEnumProperty* EnumProp = CastField<FEnumProperty>(Property))
	{
		FString EnumText;
		if (!JsonValue->TryGetString(EnumText))
		{
			AddError(OutErrors, FString::Printf(TEXT("Property '%s': expected enum string"), *Property->GetName()));
			return false;
		}

		const UEnum* Enum = EnumProp->GetEnum();
		const int64 EnumValue = Enum ? Enum->GetValueByNameString(EnumText) : INDEX_NONE;
		if (EnumValue == INDEX_NONE)
		{
			AddError(OutErrors, FString::Printf(TEXT("Property '%s': invalid enum value '%s'"),
				*Property->GetName(), *EnumText));
			return false;
		}

		if (!bValidationOnly)
		{
			EnumProp->GetUnderlyingProperty()->SetIntPropertyValue(WorkingPtr, EnumValue);
		}
		return true;
	}

	if (const FByteProperty* ByteProp = CastField<FByteProperty>(Property))
	{
		if (ByteProp->Enum)
		{
			FString EnumText;
			if (!JsonValue->TryGetString(EnumText))
			{
				AddError(OutErrors, FString::Printf(TEXT("Property '%s': expected enum string"), *Property->GetName()));
				return false;
			}

			const int64 EnumValue = ByteProp->Enum->GetValueByNameString(EnumText);
			if (EnumValue == INDEX_NONE)
			{
				AddError(OutErrors, FString::Printf(TEXT("Property '%s': invalid enum value '%s'"),
					*Property->GetName(), *EnumText));
				return false;
			}

			if (!bValidationOnly)
			{
				ByteProp->SetIntPropertyValue(WorkingPtr, EnumValue);
			}
			return true;
		}

		double NumberValue = 0.0;
		if (!JsonValue->TryGetNumber(NumberValue))
		{
			AddError(OutErrors, FString::Printf(TEXT("Property '%s': expected numeric value"), *Property->GetName()));
			return false;
		}
		if (!bValidationOnly)
		{
			ByteProp->SetIntPropertyValue(WorkingPtr, static_cast<int64>(NumberValue));
		}
		return true;
	}

	if (const FNumericProperty* NumericProp = CastField<FNumericProperty>(Property))
	{
		double NumberValue = 0.0;
		if (!JsonValue->TryGetNumber(NumberValue))
		{
			AddError(OutErrors, FString::Printf(TEXT("Property '%s': expected numeric value"), *Property->GetName()));
			return false;
		}

		if (!bValidationOnly)
		{
			if (NumericProp->IsInteger())
			{
				NumericProp->SetIntPropertyValue(WorkingPtr, static_cast<int64>(NumberValue));
			}
			else if (NumericProp->IsFloatingPoint())
			{
				NumericProp->SetFloatingPointPropertyValue(WorkingPtr, NumberValue);
			}
		}

		return true;
	}

	if (const FStrProperty* StrProp = CastField<FStrProperty>(Property))
	{
		FString StringValue;
		if (!JsonValue->TryGetString(StringValue))
		{
			AddError(OutErrors, FString::Printf(TEXT("Property '%s': expected string value"), *Property->GetName()));
			return false;
		}
		if (!bValidationOnly)
		{
			StrProp->SetPropertyValue(WorkingPtr, StringValue);
		}
		return true;
	}

	if (const FNameProperty* NameProp = CastField<FNameProperty>(Property))
	{
		FString StringValue;
		if (!JsonValue->TryGetString(StringValue))
		{
			AddError(OutErrors, FString::Printf(TEXT("Property '%s': expected string value"), *Property->GetName()));
			return false;
		}
		if (!bValidationOnly)
		{
			NameProp->SetPropertyValue(WorkingPtr, FName(*StringValue));
		}
		return true;
	}

	if (const FTextProperty* TextProp = CastField<FTextProperty>(Property))
	{
		FString StringValue;
		if (!JsonValue->TryGetString(StringValue))
		{
			AddError(OutErrors, FString::Printf(TEXT("Property '%s': expected string value"), *Property->GetName()));
			return false;
		}
		if (!bValidationOnly)
		{
			TextProp->SetPropertyValue(WorkingPtr, FText::FromString(StringValue));
		}
		return true;
	}

	if (const FArrayProperty* ArrayProp = CastField<FArrayProperty>(Property))
	{
		const TArray<TSharedPtr<FJsonValue>>* JsonArray = nullptr;
		if (!JsonValue->TryGetArray(JsonArray) || !JsonArray)
		{
			AddError(OutErrors, FString::Printf(TEXT("Property '%s': expected array value"), *Property->GetName()));
			return false;
		}

		FScriptArrayHelper ArrayHelper(ArrayProp, WorkingPtr);
		if (!bValidationOnly)
		{
			ArrayHelper.Resize(JsonArray->Num());
		}

		bool bArraySuccess = true;
		for (int32 Index = 0; Index < JsonArray->Num(); ++Index)
		{
			if (bValidationOnly)
			{
				FTemporaryPropertyStorage ElementStorage(ArrayProp->Inner);
				bArraySuccess &= ApplyJsonValueToPropertyInternal(ArrayProp->Inner,
					ElementStorage.Data, OwnerObject, (*JsonArray)[Index], OutErrors, true);
				continue;
			}

			bArraySuccess &= ApplyJsonValueToPropertyInternal(ArrayProp->Inner,
				ArrayHelper.GetRawPtr(Index), OwnerObject, (*JsonArray)[Index], OutErrors, false);
		}

		return bArraySuccess;
	}

	if (const FSetProperty* SetProp = CastField<FSetProperty>(Property))
	{
		const TArray<TSharedPtr<FJsonValue>>* JsonArray = nullptr;
		if (!JsonValue->TryGetArray(JsonArray) || !JsonArray)
		{
			AddError(OutErrors, FString::Printf(TEXT("Property '%s': expected array value for set"), *Property->GetName()));
			return false;
		}

		bool bSetSuccess = true;
		if (!bValidationOnly)
		{
			FScriptSetHelper SetHelper(SetProp, WorkingPtr);
			SetHelper.EmptyElements(JsonArray->Num());

			for (int32 Index = 0; Index < JsonArray->Num(); ++Index)
			{
				const int32 AddedIndex = SetHelper.AddDefaultValue_Invalid_NeedsRehash();
				bSetSuccess &= ApplyJsonValueToPropertyInternal(SetProp->ElementProp,
					SetHelper.GetElementPtr(AddedIndex), OwnerObject, (*JsonArray)[Index], OutErrors, false);
			}
			SetHelper.Rehash();
		}
		else
		{
			for (const TSharedPtr<FJsonValue>& ElementValue : *JsonArray)
			{
				FTemporaryPropertyStorage ElementStorage(SetProp->ElementProp);
				bSetSuccess &= ApplyJsonValueToPropertyInternal(SetProp->ElementProp,
					ElementStorage.Data, OwnerObject, ElementValue, OutErrors, true);
			}
		}

		return bSetSuccess;
	}

	if (const FMapProperty* MapProp = CastField<FMapProperty>(Property))
	{
		const TSharedPtr<FJsonObject> JsonObject = JsonValue->AsObject();
		if (!JsonObject.IsValid())
		{
			AddError(OutErrors, FString::Printf(TEXT("Property '%s': expected object value for map"), *Property->GetName()));
			return false;
		}

		bool bMapSuccess = true;
		if (!bValidationOnly)
		{
			FScriptMapHelper MapHelper(MapProp, WorkingPtr);
			MapHelper.EmptyValues(JsonObject->Values.Num());

			for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : JsonObject->Values)
			{
				const int32 AddedIndex = MapHelper.AddDefaultValue_Invalid_NeedsRehash();
				FString KeyText = Pair.Key;
				if (!MapProp->KeyProp->ImportText_Direct(*KeyText, MapHelper.GetKeyPtr(AddedIndex), OwnerObject, PPF_None))
				{
					AddError(OutErrors, FString::Printf(TEXT("Property '%s': failed to parse map key '%s'"),
						*Property->GetName(), *Pair.Key));
					bMapSuccess = false;
				}
				bMapSuccess &= ApplyJsonValueToPropertyInternal(MapProp->ValueProp,
					MapHelper.GetValuePtr(AddedIndex), OwnerObject, Pair.Value, OutErrors, false);
			}
			MapHelper.Rehash();
		}
		else
		{
			for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : JsonObject->Values)
			{
				FTemporaryPropertyStorage KeyStorage(MapProp->KeyProp);
				if (!MapProp->KeyProp->ImportText_Direct(*Pair.Key, KeyStorage.Data, OwnerObject, PPF_None))
				{
					AddError(OutErrors, FString::Printf(TEXT("Property '%s': failed to parse map key '%s'"),
						*Property->GetName(), *Pair.Key));
					bMapSuccess = false;
				}

				FTemporaryPropertyStorage ValueStorage(MapProp->ValueProp);
				bMapSuccess &= ApplyJsonValueToPropertyInternal(MapProp->ValueProp,
					ValueStorage.Data, OwnerObject, Pair.Value, OutErrors, true);
			}
		}

		return bMapSuccess;
	}

	if (const FStructProperty* StructProp = CastField<FStructProperty>(Property))
	{
		// FGameplayTag requires creation through RequestGameplayTag for proper
		// tag-manager registration.  Generic ImportText / JsonObjectToUStruct
		// only sets the raw TagName FName, producing a tag that appears valid in
		// memory but is unrecognised by the gameplay-tag system and silently
		// reverts to empty on the next serialisation round-trip.
		{
			const int32 ErrorCountBefore = OutErrors.Num();
			if (TryApplyGameplayTagValue(StructProp, WorkingPtr, JsonValue, OutErrors, bValidationOnly))
			{
				return OutErrors.Num() == ErrorCountBefore;
			}
		}

		// IMPORTANT: Check Type before calling AsObject(). UE's FJsonValueString::AsObject()
		// returns a non-null TSharedPtr wrapping an empty FJsonObject instead of nullptr,
		// which would cause this branch to be taken for string values and prevent the
		// ImportText_Direct fallback from running (needed for FGameplayTagContainer, etc.).
		if (JsonValue->Type == EJson::Object)
		{
			const TSharedPtr<FJsonObject> StructValue = JsonValue->AsObject();
			// Try FJsonObjectConverter first (handles simple structs: FVector, FRotator, etc.)
			const bool bConverted = FJsonObjectConverter::JsonObjectToUStruct(
				StructValue.ToSharedRef(), StructProp->Struct, WorkingPtr);
			if (bConverted)
			{
				return true;
			}

			// Fallback: recursive field-by-field application for complex structs
			// (e.g. FAnimNode_ModifyBone) where bulk conversion fails due to
			// internal properties that are not safe for JSON deserialization.
			bool bFieldSuccess = true;
			for (const auto& FieldPair : StructValue->Values)
			{
				FProperty* FieldProp = FindFProperty<FProperty>(StructProp->Struct, FName(*FieldPair.Key));
				if (!FieldProp)
				{
					AddError(OutErrors, FString::Printf(TEXT("Property '%s.%s': not found on struct '%s'"),
						*Property->GetName(), *FieldPair.Key, *StructProp->Struct->GetName()));
					bFieldSuccess = false;
					continue;
				}
				void* FieldPtr = FieldProp->ContainerPtrToValuePtr<void>(WorkingPtr);
				bFieldSuccess &= ApplyJsonValueToPropertyInternal(
					FieldProp, FieldPtr, OwnerObject, FieldPair.Value, OutErrors, bValidationOnly);
			}
			return bFieldSuccess;
		}

		FString StringValue;
		if (!JsonValue->TryGetString(StringValue))
		{
			AddError(OutErrors, FString::Printf(TEXT("Property '%s': expected object or string for struct"),
				*Property->GetName()));
			return false;
		}

		const TCHAR* ImportResult = Property->ImportText_Direct(*StringValue, WorkingPtr, OwnerObject, PPF_None);
		if (!ImportResult)
		{
			AddError(OutErrors, FString::Printf(TEXT("Property '%s': failed to import struct value '%s'"),
				*Property->GetName(), *StringValue));
			return false;
		}

		return true;
	}

	if (const FSoftObjectProperty* SoftObjectProperty = CastField<FSoftObjectProperty>(Property))
	{
		if (JsonValue->Type == EJson::Null)
		{
			if (!bValidationOnly)
			{
				SoftObjectProperty->SetPropertyValue(WorkingPtr, FSoftObjectPtr());
			}
			return true;
		}

		FString PathValue;
		if (!JsonValue->TryGetString(PathValue))
		{
			AddError(OutErrors, FString::Printf(TEXT("Property '%s': expected string path"), *Property->GetName()));
			return false;
		}

		if (!bValidationOnly)
		{
			SoftObjectProperty->SetPropertyValue(WorkingPtr, FSoftObjectPtr(FSoftObjectPath(PathValue)));
		}
		return true;
	}

	if (const FSoftClassProperty* SoftClassProperty = CastField<FSoftClassProperty>(Property))
	{
		if (JsonValue->Type == EJson::Null)
		{
			if (!bValidationOnly)
			{
				SoftClassProperty->SetPropertyValue(WorkingPtr, FSoftObjectPtr());
			}
			return true;
		}

		FString PathValue;
		if (!JsonValue->TryGetString(PathValue))
		{
			AddError(OutErrors, FString::Printf(TEXT("Property '%s': expected string path"), *Property->GetName()));
			return false;
		}

		if (!bValidationOnly)
		{
			SoftClassProperty->SetPropertyValue(WorkingPtr, FSoftObjectPtr(FSoftObjectPath(PathValue)));
		}
		return true;
	}

	if (const FClassProperty* ClassProperty = CastField<FClassProperty>(Property))
	{
		if (JsonValue->Type == EJson::Null)
		{
			if (!bValidationOnly)
			{
				ClassProperty->SetObjectPropertyValue(WorkingPtr, nullptr);
			}
			return true;
		}

		FString PathValue;
		if (!JsonValue->TryGetString(PathValue))
		{
			AddError(OutErrors, FString::Printf(TEXT("Property '%s': expected string class path"), *Property->GetName()));
			return false;
		}

		UClass* LoadedClass = FAuthoringHelpers::ResolveClass(PathValue, ClassProperty->MetaClass);
		if (!LoadedClass)
		{
			AddError(OutErrors, FString::Printf(TEXT("Property '%s': failed to load class '%s'"),
				*Property->GetName(), *PathValue));
			return false;
		}

		if (!bValidationOnly)
		{
			ClassProperty->SetObjectPropertyValue(WorkingPtr, LoadedClass);
		}
		return true;
	}

	if (const FObjectPropertyBase* ObjectProperty = CastField<FObjectPropertyBase>(Property))
	{
		const bool bObjectResult = ApplyObjectReference(ObjectProperty, WorkingPtr, OwnerObject, JsonValue, OutErrors, bValidationOnly);
		return bObjectResult;
	}

	FString StringValue;
	if (!JsonValue->TryGetString(StringValue))
	{
		AddError(OutErrors, FString::Printf(TEXT("Property '%s': unsupported JSON value for property type '%s'"),
			*Property->GetName(), *Property->GetClass()->GetName()));
		return false;
	}

	const TCHAR* ImportResult = Property->ImportText_Direct(*StringValue, WorkingPtr, OwnerObject, PPF_None);
	if (!ImportResult)
	{
		AddError(OutErrors, FString::Printf(TEXT("Property '%s': failed to import value '%s'"),
			*Property->GetName(), *StringValue));
		return false;
	}

	return true;
}

} // namespace PropertySerializerInternal

bool FPropertySerializer::ApplyJsonValueToProperty(const FProperty* Property,
                                                   void* ValuePtr,
                                                   UObject* OwnerObject,
                                                   const TSharedPtr<FJsonValue>& JsonValue,
                                                   TArray<FString>& OutErrors,
                                                   const bool bValidationOnly)
{
	return PropertySerializerInternal::ApplyJsonValueToPropertyInternal(
		Property, ValuePtr, OwnerObject, JsonValue, OutErrors, bValidationOnly);
}

bool FPropertySerializer::ApplyPropertiesFromJson(UObject* Target,
                                                  const TSharedPtr<FJsonObject>& PropertiesJson,
                                                  TArray<FString>& OutErrors,
                                                  const bool bValidationOnly,
                                                  const bool bRequireEditableProperty)
{
	if (!Target || !PropertiesJson.IsValid())
	{
		return true;
	}

	bool bSuccess = true;
	const UClass* TargetClass = Target->GetClass();

	for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : PropertiesJson->Values)
	{
		FProperty* Property = PropertySerializerInternal::FindPropertyOnClassHierarchy(TargetClass, FName(*Pair.Key));
		if (!Property)
		{
			PropertySerializerInternal::AddError(
				OutErrors,
				PropertySerializerInternal::BuildPropertyNotFoundMessage(TargetClass, Pair.Key));
			bSuccess = false;
			continue;
		}

		if (bRequireEditableProperty && !Property->HasAnyPropertyFlags(CPF_Edit | CPF_BlueprintVisible))
		{
			PropertySerializerInternal::AddError(
				OutErrors,
				FString::Printf(TEXT("Property '%s' is not editable on class '%s'"),
					*Pair.Key, *TargetClass->GetName()));
			bSuccess = false;
			continue;
		}

		PropertySerializerInternal::MaybeEnableOverrideFlag(Target, PropertiesJson, Property, bValidationOnly);

		void* ValuePtr = Property->ContainerPtrToValuePtr<void>(Target);
		bSuccess &= ApplyJsonValueToProperty(Property, ValuePtr, Target, Pair.Value, OutErrors, bValidationOnly);
	}

	return bSuccess;
}
