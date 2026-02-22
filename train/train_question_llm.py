#!/usr/bin/env python3
"""
TELOS — Fine-tune GPT-2 with LoRA for question generation.

Trains in 4 rounds of 3 epochs each (~5 min per round), saving between rounds.
This ensures the model is saved even if a round gets interrupted.

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
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    DataCollatorForLanguageModeling,
)
from peft import LoraConfig, get_peft_model, TaskType, PeftModel
from torch.utils.data import Dataset

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DATA_PATH = "train/data/question_sft_data.jsonl"
MODEL_NAME = "gpt2"
OUTPUT_DIR = "ali/trained_models/question_llm"
MAX_LENGTH = 256

ROUNDS = 4
EPOCHS_PER_ROUND = 3


class QuestionSFTDataset(Dataset):
    """Dataset for question generation fine-tuning."""

    def __init__(self, data_path: str, tokenizer,
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


def save_model(model, tokenizer, output_dir):
    """Save the LoRA adapter and tokenizer."""
    os.makedirs(output_dir, exist_ok=True)
    try:
        model.save_pretrained(output_dir, safe_serialization=True)
    except Exception:
        # Fallback if model card template is missing
        model.base_model.save_pretrained(output_dir, safe_serialization=True)
    # Remove auto-generated README
    readme = os.path.join(output_dir, "README.md")
    if os.path.exists(readme):
        os.remove(readme)
    tokenizer.save_pretrained(output_dir)


def load_model_for_round(round_num, tokenizer, device):
    """Load the model — fresh LoRA for round 1, resume from saved for rounds 2+."""
    base_model = GPT2LMHeadModel.from_pretrained(MODEL_NAME)

    if round_num > 1 and os.path.exists(os.path.join(OUTPUT_DIR, "adapter_config.json")):
        print(f"   📂 Resuming from saved adapter ({OUTPUT_DIR})")
        peft_model = PeftModel.from_pretrained(base_model, OUTPUT_DIR)
        # Unfreeze LoRA params for continued training
        for name, param in peft_model.named_parameters():
            if "lora" in name.lower():
                param.requires_grad = True
    else:
        print("   🔧 Creating fresh LoRA adapter...")
        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=16,
            lora_alpha=32,
            lora_dropout=0.05,
            target_modules=["c_attn", "c_proj"],
            bias="none",
        )
        peft_model = get_peft_model(base_model, lora_config)

    trainable = sum(p.numel() for p in peft_model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in peft_model.parameters())
    print(f"   ✅ {trainable/1e6:.2f}M trainable / {total/1e6:.0f}M total")
    return peft_model


def test_generation(model, tokenizer, device):
    """Quick test of the trained model."""
    model.eval()
    model = model.to(device)

    test_prompts = [
        "[MISSION] Create a website [KNOWN] nothing yet [UNKNOWN] main content purpose (100), target audience (95), pages structure (90) [QUESTION]",
        "[MISSION] Run a marketing campaign [KNOWN] target audience [UNKNOWN] campaign goal (100), campaign channels (90), key message (85) [QUESTION]",
        "[MISSION] Build a mobile app [KNOWN] app purpose [UNKNOWN] target users (95), core features (90), platform (85) [QUESTION]",
    ]

    for prompt in test_prompts:
        inputs = tokenizer(prompt, return_tensors="pt").to(device)
        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=60,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                repetition_penalty=1.2,
                pad_token_id=tokenizer.eos_token_id,
            )
        generated = tokenizer.decode(output[0], skip_special_tokens=True)
        if "[QUESTION]" in generated:
            question = generated.split("[QUESTION]")[-1].strip()
        else:
            question = generated[len(prompt):].strip()
        question = question.split("\n")[0].strip()
        if question and not question.endswith("?"):
            question = question.split("?")[0] + "?" if "?" in question else question
        print(f"  📝 {prompt[:60]}...")
        print(f"  💡 {question[:100]}")
        print()


def main():
    global_start = time.time()

    print("╔══════════════════════════════════════════════════════════╗")
    print("║    🧠 TELOS — Question LLM Training (4 rounds)        ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"   {ROUNDS} rounds × {EPOCHS_PER_ROUND} epochs = {ROUNDS * EPOCHS_PER_ROUND} total epochs")
    print()

    if not os.path.exists(DATA_PATH):
        print("⚠️  No training data. Run: python3 train/generate_question_sft.py")
        sys.exit(1)

    # Detect device
    if torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"
    print(f"📱 Device: {device}")

    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    tokenizer.pad_token = tokenizer.eos_token

    # Load dataset
    print(f"📊 Loading data from {DATA_PATH}...")
    dataset = QuestionSFTDataset(DATA_PATH, tokenizer, MAX_LENGTH)
    train_size = int(0.9 * len(dataset))
    eval_size = len(dataset) - train_size
    train_dataset, eval_dataset = torch.utils.data.random_split(
        dataset, [train_size, eval_size]
    )
    print(f"   ✅ {len(dataset)} examples (train: {train_size}, eval: {eval_size})")

    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    # --- Run 4 training rounds ---
    for round_num in range(1, ROUNDS + 1):
        round_start = time.time()
        print()
        print(f"{'═' * 58}")
        print(f"  🎯 ROUND {round_num}/{ROUNDS}  (epochs {(round_num-1)*EPOCHS_PER_ROUND+1}-{round_num*EPOCHS_PER_ROUND})")
        print(f"{'═' * 58}")

        # Load model (fresh or from previous save)
        model = load_model_for_round(round_num, tokenizer, device)

        # Adjust learning rate: decay across rounds
        lr = 5e-4 * (0.6 ** (round_num - 1))  # 5e-4, 3e-4, 1.8e-4, 1.08e-4

        training_args = TrainingArguments(
            output_dir=os.path.join(OUTPUT_DIR, "tmp_checkpoints"),
            num_train_epochs=EPOCHS_PER_ROUND,
            per_device_train_batch_size=4,
            per_device_eval_batch_size=4,
            learning_rate=lr,
            weight_decay=0.01,
            warmup_steps=30,
            logging_steps=50,
            eval_strategy="epoch",
            save_strategy="no",
            fp16=False,
            report_to="none",
            dataloader_num_workers=0,
            gradient_accumulation_steps=2,
            lr_scheduler_type="cosine",
        )

        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            data_collator=data_collator,
        )

        print(f"   LR: {lr:.1e} | Batch: 4 | Grad accum: 2")
        train_result = trainer.train()
        round_elapsed = time.time() - round_start

        # Save after each round
        print(f"\n   💾 Saving model after round {round_num}...")
        save_model(model, tokenizer, OUTPUT_DIR)

        print(f"   ✅ Round {round_num} done in {round_elapsed/60:.1f} min "
              f"| loss: {train_result.training_loss:.4f}")

        # Clean up tmp checkpoints
        import shutil
        tmp = os.path.join(OUTPUT_DIR, "tmp_checkpoints")
        if os.path.exists(tmp):
            shutil.rmtree(tmp, ignore_errors=True)

        # Free memory
        del model, trainer
        torch.mps.empty_cache() if device == "mps" else None

    # --- Final test ---
    total_elapsed = time.time() - global_start
    print()
    print(f"{'═' * 58}")
    print("🧪 Testing final model...")
    print(f"{'═' * 58}")

    base = GPT2LMHeadModel.from_pretrained(MODEL_NAME)
    final_model = PeftModel.from_pretrained(base, OUTPUT_DIR)
    test_generation(final_model, tokenizer, device)

    print("╔══════════════════════════════════════════════════════════╗")
    print("║       ✅ QUESTION LLM TRAINING COMPLETE                ║")
    print(f"║  ⏱️  Total: {total_elapsed/60:.1f} min ({ROUNDS} rounds × ~5 min)            ║")
    print(f"║  💾  Model: {OUTPUT_DIR:<38}   ║")
    print("╚══════════════════════════════════════════════════════════╝")


if __name__ == "__main__":
    main()
