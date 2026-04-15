#include "Extractors/WidgetTreeExtractor.h"
#include "PropertySerializer.h"
#include "WidgetBlueprint.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Widget.h"
#include "Components/PanelWidget.h"
#include "Components/PanelSlot.h"

TSharedPtr<FJsonObject> FWidgetTreeExtractor::Extract(const UWidgetBlueprint* WidgetBP)
{
	if (!ensureMsgf(WidgetBP, TEXT("WidgetTreeExtractor: null WidgetBlueprint")))
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
	const UWidgetTree* WidgetTree = WidgetBP->WidgetTree;
	if (!WidgetTree)
	{
		Result->SetStringField(TEXT("widgetTreeStatus"), TEXT("missing_widget_tree"));
		Result->SetField(TEXT("rootWidget"), MakeShared<FJsonValueNull>());
		Result->SetStringField(TEXT("widgetTreeError"), TEXT("WidgetTree is null on the WidgetBlueprint."));
		return Result;
	}

	const UWidget* RootWidget = WidgetTree->RootWidget;
	if (RootWidget)
	{
		const TSharedPtr<FJsonObject> RootWidgetJson = ExtractWidget(RootWidget);
		if (RootWidgetJson)
		{
			Result->SetObjectField(TEXT("rootWidget"), RootWidgetJson);
			Result->SetStringField(TEXT("widgetTreeStatus"), TEXT("ok"));
		}
		else
		{
			Result->SetField(TEXT("rootWidget"), MakeShared<FJsonValueNull>());
			Result->SetStringField(TEXT("widgetTreeStatus"), TEXT("root_widget_extract_failed"));
			Result->SetStringField(TEXT("widgetTreeError"), TEXT("Root widget exists but could not be serialized."));
		}
	}
	else
	{
		Result->SetField(TEXT("rootWidget"), MakeShared<FJsonValueNull>());
		Result->SetStringField(TEXT("widgetTreeStatus"), TEXT("missing_root_widget"));
		Result->SetStringField(TEXT("widgetTreeError"), TEXT("WidgetTree exists but RootWidget is null."));
	}

	const TSharedPtr<FJsonObject> BindingsJson = ExtractBindings(WidgetBP);
	if (BindingsJson && 0 < BindingsJson->Values.Num())
	{
		Result->SetObjectField(TEXT("bindings"), BindingsJson);
	}

	return Result;
}

TSharedPtr<FJsonObject> FWidgetTreeExtractor::ExtractWidget(const UWidget* Widget)
{
	if (!Widget)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Obj = MakeShared<FJsonObject>();

	Obj->SetStringField(TEXT("name"), Widget->GetName());
	Obj->SetStringField(TEXT("class"), Widget->GetClass()->GetFName().ToString());

	const FString DisplayLabel = Widget->GetDisplayLabel();
	if (DisplayLabel != Widget->GetName())
	{
		Obj->SetStringField(TEXT("displayLabel"), DisplayLabel);
	}

	Obj->SetBoolField(TEXT("isVariable"), Widget->bIsVariable);

	const ESlateVisibility Visibility = Widget->GetVisibility();
	const FString VisibilityStr = VisibilityToString(Visibility);
	if (VisibilityStr != TEXT("Visible"))
	{
		Obj->SetStringField(TEXT("visibility"), VisibilityStr);
	}

	if (Widget->Slot)
	{
		const TSharedPtr<FJsonObject> SlotJson = ExtractSlot(Widget->Slot);
		if (SlotJson && 0 < SlotJson->Values.Num())
		{
			Obj->SetObjectField(TEXT("slot"), SlotJson);
		}
	}

	const TSharedPtr<FJsonObject> PropertiesJson = ExtractPropertyOverrides(Widget);
	if (PropertiesJson && 0 < PropertiesJson->Values.Num())
	{
		Obj->SetObjectField(TEXT("properties"), PropertiesJson);
	}

	const UPanelWidget* Panel = Cast<UPanelWidget>(Widget);
	if (Panel)
	{
		TArray<TSharedPtr<FJsonValue>> ChildArray;

		for (int32 i = 0; i < Panel->GetChildrenCount(); ++i)
		{
			const UWidget* Child = Panel->GetChildAt(i);
			const TSharedPtr<FJsonObject> ChildJson = ExtractWidget(Child);
			if (ChildJson)
			{
				ChildArray.Add(MakeShared<FJsonValueObject>(ChildJson));
			}
		}

		if (0 < ChildArray.Num())
		{
			Obj->SetArrayField(TEXT("children"), ChildArray);
		}
	}

	return Obj;
}

TSharedPtr<FJsonObject> FWidgetTreeExtractor::ExtractSlot(const UPanelSlot* Slot)
{
	if (!Slot)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Obj = MakeShared<FJsonObject>();

	Obj->SetStringField(TEXT("slotClass"), Slot->GetClass()->GetFName().ToString());

	const TSharedPtr<FJsonObject> SlotProperties = ExtractPropertyOverrides(Slot);
	if (SlotProperties)
	{
		for (const auto& Pair : SlotProperties->Values)
		{
			Obj->SetField(Pair.Key, Pair.Value);
		}
	}

	return Obj;
}

TSharedPtr<FJsonObject> FWidgetTreeExtractor::ExtractPropertyOverrides(const UObject* Object)
{
	return FPropertySerializer::SerializePropertyOverrides(Object);
}

TSharedPtr<FJsonObject> FWidgetTreeExtractor::ExtractBindings(const UWidgetBlueprint* WidgetBP)
{
	if (!WidgetBP)
	{
		return nullptr;
	}

	const TArray<FDelegateEditorBinding>& Bindings = WidgetBP->Bindings;
	if (Bindings.Num() == 0)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> BindingsObj = MakeShared<FJsonObject>();

	for (const FDelegateEditorBinding& Binding : Bindings)
	{
		const FString Key = Binding.ObjectName + TEXT(".") + Binding.PropertyName.ToString();
		const FString Value = Binding.FunctionName.ToString();
		BindingsObj->SetStringField(Key, Value);
	}

	return BindingsObj;
}

FString FWidgetTreeExtractor::VisibilityToString(const ESlateVisibility Visibility)
{
	return StaticEnum<ESlateVisibility>()->GetNameStringByValue(static_cast<int64>(Visibility));
}
