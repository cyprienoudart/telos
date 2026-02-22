#!/usr/bin/env python3
"""
TELOS — Fine-tune GPT-2 with LoRA for mission identification (C1).

Takes the C1 SFT data (mission text → category + elements with scores) and
fine-tunes GPT-2 using PEFT/LoRA so it learns to identify task categories
and element checklists from user descriptions.

Runs on Apple Silicon MPS or CPU.
"""
from __future__ import annotations

import json
import os
import sys
import time

import torch
from transformers import (
    GPT2LMHeadModel,
    GPT2Tokenizer,
    Trainer,
    TrainingArguments,
    DataCollatorForLanguageModeling,
)
from peft import LoraConfig, get_peft_model, TaskType
from torch.utils.data import Dataset

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DATA_PATH = "training_data/c1_sft_data.jsonl"
MODEL_NAME = "gpt2"
OUTPUT_DIR = "ali/trained_models/c1_llm"
MAX_LENGTH = 512  # C1 outputs can be long (full element lists with scores)


class C1SFTDataset(Dataset):
    """Dataset for C1 mission identification fine-tuning."""

    def __init__(self, data_path: str, tokenizer: GPT2Tokenizer,
                 max_length: int = MAX_LENGTH):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.examples = []

        with open(data_path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    item = json.loads(line)
                    self.examples.append(item["text"])

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        text = self.examples[idx]
        encoding = self.tokenizer(
            text,
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_tensors="pt",
        )
        input_ids = encoding["input_ids"].squeeze()
        attention_mask = encoding["attention_mask"].squeeze()
        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": input_ids.clone(),
        }


def main():
    start_time = time.time()

    print("╔══════════════════════════════════════════════════════════╗")
    print("║   🧠 TELOS — Fine-tuning Mission Identifier LLM (C1)  ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    # Check for training data
    if not os.path.exists(DATA_PATH):
        print("⚠️  No training data found. Run generate_c1_sft.py first.")
        print("   python3 training_data/generate_c1_sft.py")
        sys.exit(1)

    # Detect device
    if torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"
    print(f"📱 Device: {device}")

    # Load tokenizer and model
    print(f"📦 Loading base model: {MODEL_NAME}...")
    tokenizer = GPT2Tokenizer.from_pretrained(MODEL_NAME)
    tokenizer.pad_token = tokenizer.eos_token

    model = GPT2LMHeadModel.from_pretrained(MODEL_NAME)
    base_params = sum(p.numel() for p in model.parameters())
    print(f"   ✅ Base model: {base_params / 1e6:.0f}M parameters")

    # Apply LoRA
    print("🔧 Applying LoRA adapter...")
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["c_attn", "c_proj"],
        bias="none",
    )
    model = get_peft_model(model, lora_config)
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"   ✅ LoRA: {trainable_params / 1e6:.2f}M trainable "
          f"({trainable_params / base_params * 100:.1f}% of base)")

    # Load dataset
    print(f"📊 Loading training data from {DATA_PATH}...")
    dataset = C1SFTDataset(DATA_PATH, tokenizer, MAX_LENGTH)
    print(f"   ✅ {len(dataset)} training examples")

    # Split into train/eval
    train_size = int(0.9 * len(dataset))
    eval_size = len(dataset) - train_size
    train_dataset, eval_dataset = torch.utils.data.random_split(
        dataset, [train_size, eval_size]
    )
    print(f"   📊 Train: {train_size}, Eval: {eval_size}")

    # Calculate training epochs — target ~15 minutes
    estimated_steps_per_sec = 1.5 if device == "mps" else 0.4  # Longer seqs = slower
    target_seconds = 15 * 60  # 15 minutes
    estimated_total_steps = int(target_seconds * estimated_steps_per_sec)
    steps_per_epoch = max(1, train_size // 4)
    num_epochs = max(5, min(20, estimated_total_steps // steps_per_epoch))

    print(f"\n🚀 Training configuration:")
    print(f"   Epochs: {num_epochs}")
    print(f"   Batch size: 4")
    print(f"   Learning rate: 5e-4")
    print(f"   Steps/epoch: ~{steps_per_epoch}")
    print(f"   Estimated total steps: ~{steps_per_epoch * num_epochs}")
    print(f"   Target duration: ~15 minutes")
    print()

    # Data collator
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,
    )

    # Training arguments
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=4,
        per_device_eval_batch_size=4,
        learning_rate=5e-4,
        weight_decay=0.01,
        warmup_steps=50,
        logging_steps=50,
        eval_strategy="steps",
        eval_steps=200,
        save_steps=500,
        save_total_limit=2,
        fp16=False,  # MPS doesn't support fp16 well
        report_to="none",
        dataloader_num_workers=0,
        gradient_accumulation_steps=2,
        lr_scheduler_type="cosine",
    )

    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=data_collator,
    )

    # Train
    print("═" * 58)
    print("🎯 Starting fine-tuning...")
    print("═" * 58)

    train_result = trainer.train()

    # Save the LoRA adapter
    print("\n💾 Saving fine-tuned model...")
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    # Test identification
    print("\n🧪 Testing mission identification...")
    model.eval()
    model = model.to(device)

    test_prompts = [
        "[MISSION] I need a website for my bakery with online ordering [IDENTIFY]",
        "[MISSION] We want to run an email marketing campaign for our new product launch [IDENTIFY]",
        "[MISSION] Build me a mobile app for fitness tracking on iOS and Android [IDENTIFY]",
        "[MISSION] I need a website and also want to set up email marketing for my restaurant [IDENTIFY]",
        "[MISSION] Create a brand identity for our tech startup [IDENTIFY]",
    ]

    for prompt in test_prompts:
        inputs = tokenizer(prompt, return_tensors="pt").to(device)
        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=200,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                repetition_penalty=1.2,
                pad_token_id=tokenizer.eos_token_id,
            )
        generated = tokenizer.decode(output[0], skip_special_tokens=True)

        # Extract the part after [IDENTIFY]
        if "[IDENTIFY]" in generated:
            identification = generated.split("[IDENTIFY]")[-1].strip()
        else:
            identification = generated[len(prompt):].strip()

        # Clean up — take first line and stop at next token marker
        identification = identification.split("\n")[0].strip()
        identification = identification.split("[")[0].strip()

        print(f"\n  📝 Mission: {prompt[10:-12]}")
        print(f"  💡 Result: {identification[:150]}")

    elapsed = time.time() - start_time
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║    ✅ C1 MISSION IDENTIFIER LLM FINE-TUNING COMPLETE   ║")
    print(f"║  ⏱️  Duration: {elapsed / 60:.1f} minutes                             ║")
    print(f"║  📊  Training loss: {train_result.training_loss:.4f}                        ║")
    print(f"║  💾  Model saved to: {OUTPUT_DIR:<30}     ║")
    print("╚══════════════════════════════════════════════════════════╝")


if __name__ == "__main__":
    main()
