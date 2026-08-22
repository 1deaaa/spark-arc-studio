"""
2026.8.12
2026.8.18
5.5.0
0.24.0
__UNSLOTH_VERSIONING__
"""

# Unsloth auto generated code
# Copyright 2023-present Daniel Han-Chen, Michael Han-Chen & the Unsloth team. All rights reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from torch import Tensor
import torch
import torch.nn as nn
from torch.nn import functional as F
from unsloth_zoo.temporary_patches.utils import torch_compile_with_fallback
from unsloth_zoo.temporary_patches.common import torch_compile
from unsloth_zoo.temporary_patches.common import _maybe_compile
import functools
from typing import Any, List, Optional, Tuple, Union, Dict, Set, Callable
from trl.trainer.grpo_trainer import (Any, AutoConfig, AutoModelForSequenceClassification, AutoProcessor, AutoTokenizer, BaseTrainer, DataLoader, Dataset, FSDP, GRPOConfig, GRPOTrainer, GenerationConfig, IterableDataset, Optional, Path, PeftConfig, PreTrainedModel, PreTrainedTokenizerBase, ProcessorMixin, RepeatSampler, RewardFunc, Sampler, SyncRefModelCallback, TrainerCallback, Union, VLLMClient, _ForwardRedirection, apply_chat_template, broadcast_object_list, datasets, defaultdict, deque, disable_dropout_in_model, ensure_master_addr_port, gather, gather_object, identity, inspect, is_conversational, is_datasets_available, is_flash_attn_2_available, is_liger_kernel_available, is_peft_model, is_rich_available, is_vllm_available, logger, logging, maybe_apply_chat_template, nanmax, nanmin, nanstd, nn, nullcontext, os, pad, partial, prepare_deepspeed, prepare_fsdp, prepare_multimodal_messages, print_prompt_completions_sample, profiling_context, profiling_decorator, seed_worker, selective_log_softmax, set_seed, shuffle_sequence_dict, split_pixel_values_by_grid, split_tensor_dict, textwrap, torch, transformers, unsplit_pixel_values_by_grid, unwrap_model_for_generation, AutoConfig, AutoModelForSequenceClassification, AutoProcessor, AutoTokenizer, Dataset, GRPOConfig, GRPOTrainer, GenerationConfig, IterableDataset, Optional, PeftConfig, PreTrainedModel, PreTrainedTokenizerBase, ProcessorMixin, RewardFunc, SyncRefModelCallback, TrainerCallback, Union, VLLMClient, datasets, defaultdict, deque, disable_dropout_in_model, ensure_master_addr_port, identity, inspect, is_liger_kernel_available, is_peft_model, is_vllm_available, logger, nn, os, pad, prepare_deepspeed, prepare_fsdp, set_seed, torch, transformers, Any, Union, gather, gather_object, is_conversational, logging, nanmax, nanmin, nanstd, os, pad, torch, FSDP, Optional, apply_chat_template, broadcast_object_list, gather, gather_object, is_flash_attn_2_available, maybe_apply_chat_template, nullcontext, os, pad, prepare_multimodal_messages, profiling_context, torch, transformers, unwrap_model_for_generation, nn, os, pad, selective_log_softmax, torch, transformers, Any, Union, profiling_decorator, shuffle_sequence_dict, split_pixel_values_by_grid, split_tensor_dict, torch, unsplit_pixel_values_by_grid, PreTrainedModel, logger, os, torch, FSDP, nn, os, FSDP, nn, torch, GRPOTrainer, gather, inspect, nanmax, nanmin, os, pad, torch)


import os
import math
import logging
from typing import *
from dataclasses import dataclass, field
from packaging.version import Version
import torch
import numpy as np
from contextlib import nullcontext
from torch.nn import functional as F
import inspect
from transformers import DataCollatorForSeq2Seq, DataCollatorForLanguageModeling as TransformersDataCollatorForLanguageModeling
from transformers.training_args import ParallelMode
from unsloth_zoo.device_type import DEVICE_TYPE, device_synchronize

# Wrap trainer with padding to right and enable training mode
import functools
from types import MethodType
try:
    from unsloth_zoo.gradient_checkpointing import reset_unsloth_gradient_checkpointing_buffers
except:
    def reset_unsloth_gradient_checkpointing_buffers(): pass
# Canonical reset lives in unsloth.models._utils so the SFT auto-packing wrapper and the plain
# Trainer loop can import the same helper; fall back to a no-op only if it can't be imported.
try:
    from unsloth.models._utils import _unsloth_reset_stray_compile_cache
except Exception:
    def _unsloth_reset_stray_compile_cache(self): pass
# Drops/renames config arguments the installed TRL no longer accepts, so a
# script pinned to an older TRL keeps working after an upgrade. Falls back to
# the historical raw passthrough so this can never break trainer construction.
try:
    from unsloth.models.rl_config_compat import filter_config_init_kwargs as _unsloth_filter_config_init_kwargs
except Exception:
    def _unsloth_filter_config_init_kwargs(config_class, kwargs): return kwargs
def prepare_for_training_mode(f):
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        # Drop any torch.compile graph cache poisoned by a stray pre-train forward.
        try:
            _unsloth_reset_stray_compile_cache(self)
        except Exception:
            pass
        # Finish the previous W&B run if this is a subsequent train() call.
        # We do this at the START of train() (not the end) so that
        # evaluate() / log() still work after train() completes.
        # HF's WandbCallback.setup() will call wandb.init() for the new run.
        # See: https://github.com/unslothai/unsloth/issues/3954
        if getattr(self, '_unsloth_training_completed', False):
            try:
                import wandb
                if wandb.run is not None:
                    wandb.finish()
                    # Reset HF's WandbCallback so it calls wandb.init() for the new run
                    for cb in self.callback_handler.callbacks:
                        if type(cb).__name__ == 'WandbCallback':
                            cb._initialized = False
                            break
            except:
                pass
        # Enable training mode
        _was_training = None
        # Restore the GC mode the model was configured with at setup; fall back to
        # the training args only when it wasn't recorded (issue #4735). Use hasattr,
        # not a None sentinel, so a deliberately-recorded None is restored verbatim.
        _model = getattr(self, 'model', None)
        if hasattr(_model, '_unsloth_gradient_checkpointing'):
            use_gc = _model._unsloth_gradient_checkpointing
        else:
            use_gc = getattr(self.args, 'gradient_checkpointing', True)
        if hasattr(self, 'model') and hasattr(self.model, "training"):
            _was_training = self.model.training
        if hasattr(self, 'model') and hasattr(self.model, "for_training"):
            self.model.for_training(use_gradient_checkpointing=use_gc)
        output = f(self, *args, **kwargs)
        # Restore previous mode when possible
        if hasattr(self, 'model') and hasattr(self.model, "for_inference"):
            if _was_training is False:
                self.model.for_inference()
            elif _was_training is True and hasattr(self.model, "for_training"):
                self.model.for_training(use_gradient_checkpointing=use_gc)
        # Reset gradient checkpointing buffers to free memory while staying ready for next run
        try:
            reset_unsloth_gradient_checkpointing_buffers()
        except:
            pass
        # Mark that training completed so the next train() call can
        # finish this W&B run before starting a new one
        self._unsloth_training_completed = True
        return output
    return wrapper
pass

torch_compile_options = {
            "epilogue_fusion"   : True,
            "max_autotune"      : False,
            "shape_padding"     : True,
            "trace.enabled"     : False,
            "triton.enable_persistent_tma_matmul": torch.cuda.get_device_capability()[0] >= 9,
            "cuda.cutlass_epilogue_fusion_enabled": torch.cuda.get_device_capability()[0] >= 9,
            "cuda.cutlass_tma_only": torch.cuda.get_device_capability()[0] >= 9,
            "cuda.compile_opt_level"              : "-O2",
            "cuda.enable_cuda_lto"                : True,
        }

@_maybe_compile(dynamic = True, fullgraph = True, options = torch_compile_options,)
def chunked_hidden_states_selective_log_softmax(
    hidden_states: torch.Tensor,
    lm_head: torch.Tensor,
    index: torch.Tensor,
    chunks: int = 4,
    logit_scale_multiply: float = 0.0,
    logit_scale_divide: float = 0.0,
    logit_softcapping: float = 0.0,
    temperature: float = 1.0,
    # Rows per chunk cap. Read HERE, in the default, not in the body: the body
    # is traced with fullgraph = True, and `os.environ` is an unsupported op
    # there on torch 2.4 -- Dynamo raises
    #   torch._dynamo.exc.Unsupported: const method call bytes.decode
    # from os._Environ.__getitem__, which the eager fallback does not catch
    # (it only catches recompile-limit and disabled-hook breaks), so the very
    # first call would die even with the variable unset. A default is evaluated
    # once when the def runs, which is import time, outside any traced region.
    # It is also a plain int argument, so Dynamo guards on it instead of
    # constant-folding an unguarded read (2.7+ never notice a later change).
    # A non-numeric value is ignored rather than raised on, so a typo cannot
    # break the import. 0 keeps the previous chunk boundaries exactly.
    max_rows_per_chunk: int = (
        int(os.environ.get("UNSLOTH_GRPO_MAX_ROWS_PER_CHUNK", "0").strip())
        if os.environ.get("UNSLOTH_GRPO_MAX_ROWS_PER_CHUNK", "0").strip().isdigit()
        else 0
    ),
) -> torch.Tensor:
    # All Unsloth Zoo code licensed under AGPL3
    # Reshape on this tensor's own last dim: a no-op, so a wrong-width caller
    # cannot have its row count silently rewritten and instead fails at the
    # matmul below, which prints both operands. Do not swap in a bare
    # torch._check: it reports only "Expected cond to be True", naming neither
    # operand, and Dynamo rejects a message-carrying one. Callers dispatch on
    # the width first -- see `compute_logprobs_chunk`, the packed path and
    # `_pg_grad_forward`.
    flat_hidden_states = hidden_states.reshape(-1, hidden_states.shape[-1])
    flat_index = index.reshape(-1)

    # Each chunk materialises rows x vocab logits and then a float32 copy of
    # them, all on the device holding the output head. With a large vocabulary
    # and a fixed chunk count that grows with the batch, so the peak scales with
    # the batch rather than staying bounded. max_rows_per_chunk caps the rows
    # per chunk instead, which is pure loop splitting: more, smaller chunks,
    # same concatenated result. 0 (the default) keeps the previous chunk
    # boundaries exactly.
    if max_rows_per_chunk > 0:
        n_rows = flat_hidden_states.shape[0]
        chunks = max(chunks, -(-n_rows // max_rows_per_chunk))
        chunks = min(chunks, max(n_rows, 1))

    chunked_hidden_states = torch.chunk(flat_hidden_states, chunks=chunks, dim=0)
    chunked_index = torch.chunk(flat_index, chunks=chunks, dim=0)

    all_per_token_logps = []

    for chunk_hidden_states, chunk_index in zip(chunked_hidden_states, chunked_index):
        # When the model is dispatched over several devices, the output head can
        # sit on a different one from the hidden states, because accelerate
        # places the tail of the model on the last device it fills. Co-locate on
        # the head's device before the matmul, otherwise this raises
        #   Unhandled FakeTensor Device Propagation for aten.mm.default,
        #   found two different devices cuda:0, cuda:1
        # On a single device every .to() here is a no-op and the result is
        # bit-identical to before.
        chunk_hidden_states = chunk_hidden_states.to(device = lm_head.device, dtype = lm_head.dtype)
        chunk_index = chunk_index.to(lm_head.device)
        chunk_logits = chunk_hidden_states @ lm_head.t()

        if logit_scale_multiply != 0.0:
            chunk_logits = chunk_logits * logit_scale_multiply
        if logit_scale_divide != 0.0:
            chunk_logits = chunk_logits / logit_scale_divide
        if logit_softcapping != 0.0:
            chunk_logits = logit_softcapping * torch.tanh(chunk_logits / logit_softcapping)

        chunk_logits = chunk_logits.to(torch.float32)

        if temperature != 1.0:
            chunk_logits = chunk_logits / temperature

        selected_logits = torch.gather(chunk_logits, dim=-1, index=chunk_index.unsqueeze(-1)).squeeze(-1)
        logsumexp_values = torch.logsumexp(chunk_logits, dim=-1)
        per_token_logps = selected_logits - logsumexp_values
        # Return to the caller's device so the concatenation below and every
        # downstream consumer see the device they started on.
        all_per_token_logps.append(per_token_logps.to(hidden_states.device))

    all_per_token_logps = torch.concat(all_per_token_logps)

    all_per_token_logps = all_per_token_logps.reshape((hidden_states.shape[0], hidden_states.shape[1]))
    return all_per_token_logps

@_maybe_compile(dynamic = True, fullgraph = True, options = torch_compile_options,)
def chunked_selective_log_softmax(
    logits,
    index,
    temperature: float = 1.0,
    chunks: int = 4,
):
    chunked_logits = torch.chunk(logits.reshape(-1, logits.shape[-1]), chunks = chunks, dim = 0)
    chunked_index  = torch.chunk(index.reshape(-1), chunks = chunks, dim = 0)
    all_per_token_logps = []
    # Per-chunk selective_log_softmax.
    for chunk_logits, chunk_index in zip(chunked_logits, chunked_index):
        chunk_logits = chunk_logits.to(torch.float32)
        if temperature != 1.0:
            chunk_logits = chunk_logits / temperature
        selected_logits = torch.gather(chunk_logits, dim = -1, index = chunk_index.unsqueeze(-1)).squeeze(-1)
        logsumexp_values = torch.logsumexp(chunk_logits, dim = -1)
        per_token_logps = selected_logits - logsumexp_values
        all_per_token_logps.append(per_token_logps)
    pass
    all_per_token_logps = torch.concat(all_per_token_logps)
    all_per_token_logps = all_per_token_logps.reshape((logits.shape[0], logits.shape[1]))
    return all_per_token_logps

def calculate_pad_tokens_in_prompt(
    input_ids: torch.Tensor,
    logits_to_keep: int,
    pad_token_id: int
) -> torch.Tensor:
    """Count left-padded tokens per sequence, e.g. [pad, pad, pad, cat] -> 3."""
    if logits_to_keep >= input_ids.shape[1]:
        raise ValueError("logits_to_keep must be smaller than the sequence length.")

    prompt_section = input_ids[:, :-logits_to_keep]

    padding_mask = (prompt_section == pad_token_id)

    pad_token_counts = padding_mask.sum(dim=1)

    return pad_token_counts

def create_completion_attention_mask(
    completion_input_ids: torch.Tensor,
    left_pad_tokens_per_prompt: torch.Tensor,
    max_left_pad: int,
    pad_token_id: int
) -> torch.Tensor:
    """Build a completion mask that zeros leading prompt and trailing pad tokens.

    For [p,p,p,c,c,c,pad,pad,pad] (p=sliced prompt, c=completion, pad=padding)
    this returns [0,0,0,1,1,1,0,0,0].
    """
    batch_size, completion_len = completion_input_ids.shape
    device = completion_input_ids.device

    num_tokens_to_mask = max_left_pad - left_pad_tokens_per_prompt

    indices = torch.arange(completion_len, device=device).unsqueeze(0)
    shift_mask = indices >= num_tokens_to_mask.unsqueeze(1)

    non_padding_mask = (completion_input_ids != pad_token_id)

    final_mask = shift_mask & non_padding_mask

    return final_mask

def left_pack_padding(tensor: torch.Tensor, pad_id: int) -> torch.Tensor:
    """Move all padding tokens in each sequence to the right."""
    mask = (tensor != pad_id)
    # stable=True since the binary mask is unordered.
    sorted_indices = torch.argsort(mask, dim=1, descending=True, stable=True)
    packed_tensor = torch.gather(tensor, 1, sorted_indices)
    return packed_tensor

def align_logprobs_with_mask(
    logprob_tensor: torch.Tensor,
    attention_mask: torch.Tensor,
    pad_value: float = 0.0
) -> torch.Tensor:
    """Align a log probability tensor with a given attention mask."""

    device = logprob_tensor.device
    batch_size, logprob_seq_len = logprob_tensor.shape
    mask_seq_len = attention_mask.shape[1]

    padded_logprobs = torch.full(
        attention_mask.shape,
        fill_value=pad_value,
        dtype=logprob_tensor.dtype,
        device=device
    )

    left_pad_counts = torch.argmax(attention_mask, dim=1)

    cols = torch.arange(logprob_seq_len, device=device)
    dest_indices = left_pad_counts.unsqueeze(1) + cols

    # Destination row indices, shape [batch_size, logprob_seq_len].
    row_indices = torch.arange(batch_size, device=device).unsqueeze(1).expand_as(dest_indices)

    # Keep only in-bounds destinations, then scatter via advanced indexing.
    valid_mask = dest_indices < mask_seq_len
    valid_rows = row_indices[valid_mask]
    valid_cols = dest_indices[valid_mask]
    valid_vals = logprob_tensor[valid_mask]
    padded_logprobs[valid_rows, valid_cols] = valid_vals

    return padded_logprobs

def align_completion_tool_mask(
    tool_mask: torch.Tensor,
    completion_mask: torch.Tensor,
) -> torch.Tensor:
    """Align a raw completion-length tool/env mask with Unsloth's repacked loss mask."""
    if tool_mask is None:
        return completion_mask
    if tool_mask.shape[0] != completion_mask.shape[0]:
        raise ValueError("tool_mask batch size must match completion_mask batch size.")

    tool_mask = tool_mask.to(device=completion_mask.device)
    if tool_mask.shape == completion_mask.shape:
        aligned_tool_mask = tool_mask
    else:
        aligned_tool_mask = align_logprobs_with_mask(
            tool_mask,
            completion_mask,
            pad_value=0,
        )
    return completion_mask * aligned_tool_mask.to(dtype=completion_mask.dtype)

def autotune_batch_and_chunks(
    total_input_rows,
    seq_len,
    hidden_size,
    vocab_size,
    dtype_bytes=16,
    multiplier=None
):
    if multiplier is None:
        final_m = max(4, seq_len // 4096)
    else:
        final_m = multiplier

    if torch.cuda.is_available():
        free_bytes, _ = torch.cuda.mem_get_info()
        limit_gb = (free_bytes / (1024**3))*.80
    elif hasattr(torch, "xpu") and torch.xpu.is_available():
        # XPU: estimate free memory as total - reserved.
        total_mem = torch.xpu.get_device_properties(0).total_memory
        reserved_mem = torch.xpu.memory_reserved()
        free_bytes = total_mem - reserved_mem
        limit_gb = (free_bytes / (1024**3)) * 0.80
    else:
        # Fallback: assume 8GB available.
        limit_gb = 8.0

    bytes_to_gb = 1024**3

    b_vals = torch.arange(total_input_rows, 0, -1, device='cpu', dtype=torch.float32)

    hidden_gb = (b_vals * seq_len * hidden_size * dtype_bytes) / bytes_to_gb

    base_logits = ((b_vals/total_input_rows) * b_vals * seq_len * vocab_size * dtype_bytes) / bytes_to_gb
    logits_gb = base_logits / final_m

    total_mem_gb = hidden_gb + logits_gb

    valid_mask = total_mem_gb <= limit_gb
    valid_indices = torch.nonzero(valid_mask, as_tuple=False)

    if valid_indices.shape[0] == 0:
        #This means your GPU will OOM
        return 4, final_m

    best_idx = valid_indices[0].item()
    final_b = int(b_vals[best_idx].item())

    return final_b, final_m

def sanitize_logprob(logprob):
    """Local port of trl.scripts.vllm_serve.sanitize_logprob.
    Filters NaN logprobs from vLLM outputs."""
    value = logprob.logprob
    if math.isnan(value):
        logging.getLogger(__name__).warning(
            f"Generated NaN logprob, token logprob '{logprob}' will be ignored"
        )
        return None
    return value
def _unsloth_grpo_autocast(self):
    """Decide the GRPO autocast once and latch it on the trainer.

    ACCELERATE_MIXED_PRECISION is process wide, so a trainer built later but run
    first would hand this trainer its precision. args belongs to this trainer.
    """
    if not hasattr(self, "_autocast_enabled"):
        args = getattr(self, "args", None)
        precision = getattr(args, "mixed_precision", None)
        use_bf16 = getattr(args, "bf16", None)
        use_fp16 = getattr(args, "fp16", None)
        if not isinstance(precision, str):
            # transformers < 5 has no args.mixed_precision, but rl.py sets the
            # fp16 / bf16 flags on this same args for every branch it takes.
            if isinstance(use_bf16, bool) and isinstance(use_fp16, bool):
                precision = "bf16" if use_bf16 else ("fp16" if use_fp16 else "no")
            else:
                precision = os.environ.get("ACCELERATE_MIXED_PRECISION", "fp16")
        self._autocast_dtype = torch.float16 if precision == "fp16" else torch.bfloat16
        # "no" is a real value: full finetuning and an explicit float32 load
        # both set it, and reading it as bfloat16 raises on a T4 or V100.
        self._autocast_enabled = precision != "no"
        self._autocast_force_float32 = False
        # Stamped by from_pretrained: UNSLOTH_FORCE_FLOAT32 is process wide, so a
        # model loaded after this trainer was built would answer for it here.
        forced = getattr(getattr(self, "model", None), "_unsloth_forced_float32", None)
        if forced is None:
            forced = os.environ.get("UNSLOTH_FORCE_FLOAT32", "0") == "1"
        if forced and precision != "bf16":
            # Gemma3 / gpt-oss set "no" but still want float16 autocast. A trainer
            # already on bf16 keeps it: float16 is what the forced list avoids.
            self._autocast_dtype = torch.float16
            self._autocast_enabled = True
            self._autocast_force_float32 = True

    return self._autocast_enabled, self._autocast_dtype

def _unsloth_grpo_autocast_kwargs(self, device_type = "cuda"):
    """torch.amp.autocast kwargs for GRPO generation."""
    enabled, dtype = _unsloth_grpo_autocast(self)
    if not getattr(self, "_autocast_force_float32", False) and torch.is_autocast_enabled(
        device_type
    ):
        # Already inside an autocast: inherit its dtype by omitting the key, since
        # autocast passes whatever it gets straight to set_autocast_dtype.
        return {"enabled": enabled}
    return {"enabled": enabled, "dtype": dtype}

def _unsloth_get_model_config(model):
    """Return HuggingFace model config, unwrapping DDP/Accelerate wrappers."""
    config = getattr(model, "config", None)
    if config is None and hasattr(model, "module"):
        config = getattr(model.module, "config", None)
    return config

def _unsloth_get_final_logit_softcapping(model):
    """Return final_logit_softcapping for a model config, falling back to the
    nested text sub-config for composite models. Handles both:
      - Gemma-4-style configs where the attribute lives on ``config.text_config``
      - T5Gemma-style composite configs where the text sub-config is only
        reachable via ``config.get_text_config()``
    Returns 0 if unset, matching the previous behaviour.
    """
    config = _unsloth_get_model_config(model)
    if config is None:
        return 0
    softcap = getattr(config, "final_logit_softcapping", None)
    if softcap is None:
        text_cfg = getattr(config, "text_config", None)
        if text_cfg is None:
            get_text_config = getattr(config, "get_text_config", None)
            if callable(get_text_config):
                try:
                    text_cfg = get_text_config()
                except (TypeError, ValueError):
                    text_cfg = None
        if text_cfg is not None and text_cfg is not config:
            softcap = getattr(text_cfg, "final_logit_softcapping", None)
    return 0 if softcap is None else softcap

def _unsloth_grpo_returns_hidden_states(model, tensor, lm_head):
    """Does ``tensor`` (a forward's ``.logits``) carry hidden states or real logits?

    ``_get_per_token_logps_and_entropies`` sets ``UNSLOTH_RETURN_HIDDEN_STATES=1``,
    but only a forward that honours the name hands hidden states back as
    ``.logits``; any other forward returns a real ``[.., vocab]`` tensor that must
    not reach the ``lm_head`` matmul.

    Primary test is an explicit signal that the forward honours the flag. Two
    exist, both set outside this file:

    * ``__UNSLOTH_SUPPORTS_RETURN_HIDDEN_STATES__`` on the generated class,
      written by ``unsloth_zoo.compiler.create_standalone_class`` exactly when
      ``apply_fused_lm_head`` gave that forward its own ``RETURN_HIDDEN_STATES``
      branch.
    * ``_unsloth_grpo_hidden_states_forward_wrapped``, set by
      ``_install_grpo_hidden_states_forward_wrapper`` in ``unsloth/models/rl.py``
      for models the compiler did not rewrite. That wrapper degrades to real
      logits when the model cannot produce hidden states, and records whether
      it did so in ``_unsloth_grpo_hidden_states_degraded`` before it returns,
      so reading the pair after a forward describes the call that just
      finished. Degradation is per call, not per model: a forward that splats
      ``**kwargs`` into a sub-module only some inputs reach can reject the
      request on one batch and honour it on the next.

    The width comparison stays as the fallback, for an ``unsloth_zoo`` old enough
    that it never writes the marker. It is decisive on its own whenever
    ``vocab_size != hidden_size``, and the signal is only allowed to overrule it
    when it is not: a model with ``vocab_size == hidden_size`` produces real
    logits that are the same width as its hidden states, which is the one case
    the shape cannot answer.
    """
    if tensor.shape[-1] != lm_head.shape[1]:
        return False  # vocab-wide: real logits, whatever any signal claims
    if lm_head.shape[0] != lm_head.shape[1]:
        return True  # hidden-wide and vocab_size != hidden_size: hidden states
    return _unsloth_grpo_hidden_states_signal(model) is not False

def _unsloth_grpo_hidden_states_signal(model):
    """``True``/``False`` if the forward honours ``UNSLOTH_RETURN_HIDDEN_STATES``.

    ``None`` when neither marker is present, i.e. there is no signal to read.
    See ``_unsloth_grpo_returns_hidden_states`` for where each marker is set.
    Walks the wrapper chain because the markers are set on whichever object the
    trainer saw, which may be the DDP module or the PEFT base model rather than
    the object handed to the logprob loop.
    """
    candidates = []
    pending = [model]
    while pending and len(candidates) < 8:
        candidate = pending.pop(0)
        if candidate is None or any(candidate is seen for seen in candidates):
            continue
        candidates.append(candidate)
        get_base_model = getattr(candidate, "get_base_model", None)
        if callable(get_base_model):
            try:
                pending.append(get_base_model())
            except Exception:
                pass
        for _attr in ("module", "base_model", "model"):
            child = getattr(candidate, _attr, None)
            if child is not None and hasattr(child, "forward"):
                pending.append(child)
    for candidate in candidates:
        if getattr(candidate, "__UNSLOTH_SUPPORTS_RETURN_HIDDEN_STATES__", False):
            return True
        if getattr(type(candidate), "__UNSLOTH_SUPPORTS_RETURN_HIDDEN_STATES__", False):
            return True
    if any(
        getattr(candidate, "_unsloth_grpo_hidden_states_forward_wrapped", False)
        for candidate in candidates
    ):
        # the wrapper honours the flag unless it recorded that this call could not
        if any(
            hasattr(candidate, "_unsloth_grpo_hidden_states_degraded") for candidate in candidates
        ):
            return not any(
                getattr(candidate, "_unsloth_grpo_hidden_states_degraded", False)
                for candidate in candidates
            )
        # an `unsloth/models/rl.py` predating the per-call attribute only ever set
        # the warn-once flag; it is the best signal such a wrapper offers
        return not any(
            getattr(candidate, "_unsloth_grpo_hidden_states_warning_issued", False)
            for candidate in candidates
        )
    return None

def _unsloth_get_mm_token_id(processing_class, attr_name, token):
    tokenizer = getattr(processing_class, "tokenizer", processing_class)
    token_id = getattr(processing_class, attr_name, None)
    if token_id is None:
        token_id = getattr(tokenizer, attr_name, None)

    convert_tokens_to_ids = getattr(tokenizer, "convert_tokens_to_ids", None)
    if token_id is None and convert_tokens_to_ids is not None:
        token_id = convert_tokens_to_ids(token)

    if type(token_id) is int and token_id >= 0:
        if token_id != getattr(tokenizer, "unk_token_id", None):
            return token_id
    return None

def _unsloth_fix_mm_token_type_ids(
    processing_class, input_ids, mm_token_type_ids = None, completion_ids = None
):
    image_token_id = _unsloth_get_mm_token_id(
        processing_class, "image_token_id", "<|image_pad|>"
    )
    video_token_id = _unsloth_get_mm_token_id(
        processing_class, "video_token_id", "<|video_pad|>"
    )

    if image_token_id is not None or video_token_id is not None:
        rebuilt = input_ids.new_zeros(input_ids.shape)
        if image_token_id is not None:
            rebuilt = rebuilt.masked_fill(input_ids == image_token_id, 1)
        if video_token_id is not None:
            rebuilt = rebuilt.masked_fill(input_ids == video_token_id, 2)
        return rebuilt

    if (
        mm_token_type_ids is not None
        and completion_ids is not None
        and mm_token_type_ids.shape[0] == input_ids.shape[0]
        and mm_token_type_ids.shape[1] + completion_ids.shape[1] == input_ids.shape[1]
    ):
        return torch.cat(
            [mm_token_type_ids, mm_token_type_ids.new_zeros(completion_ids.shape)],
            dim = 1,
        )
    return mm_token_type_ids

def _unsloth_clear_stateful_mrope(model):
    modules = getattr(model, "modules", None)
    if modules is None:
        return False

    cleared = False
    for module in modules():
        if hasattr(module, "compute_3d_position_ids") and hasattr(module, "rope_deltas"):
            module.rope_deltas = None
            cleared = True
    return cleared

def grpo_compute_loss(
    ref,
    new,
    old,
    sampling_per_token_logps,
    input_ids,
    mask,
    beta,
    advantages,
    **kwargs
):
    # All Unsloth Zoo code licensed under AGPL3
    # Optional argument defaults.
    loss_type = kwargs.get("loss_type", "grpo")
    epsilon_low = kwargs.get("epsilon_low", 0.2)
    epsilon_high = kwargs.get("epsilon_high", 0.2)
    max_completion_length = kwargs.get("max_completion_length", 8192)
    delta = kwargs.get("delta", None)
    importance_sampling_level = kwargs.get("importance_sampling_level", "token")
    num_items_in_batch = kwargs.get("num_items_in_batch", None)
    current_gradient_accumulation_steps = kwargs.get("current_gradient_accumulation_steps", 1)
    num_processes = kwargs.get("num_processes", 1)
    use_vllm = kwargs.get("use_vllm", False)
    vllm_importance_sampling_mode = kwargs.get("vllm_importance_sampling_mode", "sequence_mask")
    vllm_importance_sampling_cap = kwargs.get("vllm_importance_sampling_cap", 2.0)
    vllm_importance_sampling_clip_min = kwargs.get("vllm_importance_sampling_clip_min", None)
    vllm_importance_sampling_clip_max = kwargs.get("vllm_importance_sampling_clip_max", 3.0)
    get_sapo_token_loss = kwargs.get("get_sapo_token_loss", None)
    sapo_temperature_pos = kwargs.get("sapo_temperature_pos", 1.0)
    sapo_temperature_neg = kwargs.get("sapo_temperature_neg", 1.05)
    get_gamma_weights = kwargs.get("get_gamma_weights", None)
    vespo_k_pos = kwargs.get("vespo_k_pos", 2.0)
    vespo_lambda_pos = kwargs.get("vespo_lambda_pos", 3.0)
    vespo_k_neg = kwargs.get("vespo_k_neg", 3.0)
    vespo_lambda_neg = kwargs.get("vespo_lambda_neg", 2.0)
    get_off_policy_mask = kwargs.get("get_off_policy_mask", None)
    off_policy_mask_threshold  = kwargs.get("off_policy_mask_threshold", None)
    input_ids = input_ids.unsqueeze(-1)

    importance_sampling_ratio = None

    # exp(new - old) and exp(ref - new) below are taken before `mask` is applied. A sequence-packed
    # logp path leaves the masked (prompt/pad) columns at 0 while a padded one fills them with a real
    # logp, so when new and old/ref disagree there those ratios can overflow to inf and inf * 0 (the
    # masked-out loss) becomes nan. Force new/old/ref to share 0 on the masked columns so both ratios
    # are exp(0) = 1 there; every loss term below multiplies by `mask`, so this changes nothing.
    if mask is not None:
        _keep = mask.to(torch.bool)
        new = torch.where(_keep, new, 0.0)
        if old is not None: old = torch.where(_keep, old, 0.0)
        if ref is not None: ref = torch.where(_keep, ref, 0.0)

    if advantages.dim() == 1:
        advantages = advantages.unsqueeze(1)

    if off_policy_mask_threshold is not None:
        off_policy_mask = get_off_policy_mask(
            advantages=advantages,
            per_token_logps=new,
            old_per_token_logps=old,
            mask=mask,
            off_policy_threshold=off_policy_mask_threshold,
        )

    with torch.no_grad():
        if use_vllm and sampling_per_token_logps is not None:
            # Filter out extra leading prompt tokens after left-padding input_ids.
            # Match TRL: aggregate log-ratios then exp (product), not sum of exp ratios.
            importance_sampling_ratio = (old - sampling_per_token_logps) * mask

            if vllm_importance_sampling_mode in ["sequence_mask", "sequence_truncate"]:
                importance_sampling_ratio = importance_sampling_ratio.sum(dim=-1, keepdim=True)

            importance_sampling_ratio = torch.exp(importance_sampling_ratio)

            if vllm_importance_sampling_mode in ["token_truncate", "sequence_truncate"]:
                importance_sampling_ratio = torch.clamp(
                    importance_sampling_ratio, 
                    min=vllm_importance_sampling_clip_min,
                    max=vllm_importance_sampling_clip_max
                )
            elif vllm_importance_sampling_mode in ["token_mask", "sequence_mask"]:
                min_val = (
                    vllm_importance_sampling_clip_min
                    if vllm_importance_sampling_clip_min is not None
                    else -math.inf
                )

                max_val = (
                    vllm_importance_sampling_clip_max
                    if vllm_importance_sampling_clip_max is not None
                    else math.inf
                )

                invalid_mis_mask = (importance_sampling_ratio < min_val) | (
                        importance_sampling_ratio > max_val
                )

                importance_sampling_ratio = importance_sampling_ratio.masked_fill(
                        invalid_mis_mask, value=0.0
                )
            else:
                raise ValueError(
                        f"Unknown vLLM importance sampling mode: {vllm_importance_sampling_mode}. Possible values are 'token_truncate', 'token_mask', 'sequence_truncate', and 'sequence_mask'."
                )
    pass

    # Must detach when old is None: exp(new - new.detach()) == 1 but keeps grads correct.
    if old is not None:
        log_ratio = new - old
    else:
        log_ratio = new - new.detach()

    if importance_sampling_level == "token":
        log_importance_weights = log_ratio
    elif importance_sampling_level == "sequence":
        log_importance_weights = (log_ratio * mask).sum(-1) / mask.sum(-1).clamp(min=1.0)
        log_importance_weights = log_importance_weights.unsqueeze(-1)
    else:
        raise ValueError(
            f"Unknown importance sampling level: {importance_sampling_level}. Possible values are 'token' "
            "and 'sequence'."
        )

    coef_1 =  torch.exp(log_importance_weights)

    # Reverse KL: low-variance low-bias estimator as used in the GRPO paper.
    if beta != 0.0:
        kl_i = torch.exp(ref - new) - (ref - new) - 1.0

    else:
        # Zeros with the correct shape.
        if importance_sampling_level == "sequence":
            kl_i = new.new_zeros(new.size(0), 1)
        else:
            kl_i = torch.zeros_like(new)

    if loss_type == "cispo":
        clamped_ratios = torch.clamp(coef_1, max=epsilon_high).detach()
        loss_i = -clamped_ratios * advantages * new
    elif loss_type in ["grpo", "bnpo", "dr_grpo", "dapo", "luspo"]:
        coef_2 = torch.clamp(coef_1, 1 - epsilon_low, 1 + epsilon_high)

        if delta is not None:
            loss_1 = torch.clamp(coef_1, max=delta) * advantages
        else:
            loss_1 = coef_1 * advantages
        pass
        loss_2 = coef_2 * advantages
        loss_i = -torch.min(loss_1, loss_2)
    elif loss_type == "sapo":
        temperatures = torch.where(advantages > 0, sapo_temperature_pos, sapo_temperature_neg)
        soft_coef_1 = torch.sigmoid(temperatures * (coef_1 - 1)) * 4 / temperatures
        loss_i = -soft_coef_1 * advantages
    elif loss_type == "vespo":
        if get_gamma_weights is None:
            raise Exception("vespo is only available in TRL 0.26.0+")
        phi_seq = get_gamma_weights(
            advantages=advantages,
            log_ratio_per_token=log_ratio,
            mask=mask,
            importance_sampling_ratio=importance_sampling_ratio,
            k_pos=vespo_k_pos,
            lambda_pos=vespo_lambda_pos,
            k_neg=vespo_k_neg,
            lambda_neg=vespo_lambda_neg,
        )
        loss_i = -phi_seq * advantages * new
    else:
        raise ValueError(f"Unknown loss type: {loss_type}")

    if off_policy_mask_threshold is not None:
        loss_i = loss_i * off_policy_mask

    if use_vllm and sampling_per_token_logps is not None:
        # vespo applies the IS ratio inside get_gamma_weights, so skip it here.
        if loss_type != "vespo":
            loss_i = loss_i * importance_sampling_ratio
        # delta for the metric.
        with torch.no_grad():
            delta = torch.abs(old - sampling_per_token_logps)
            delta = delta * mask
            flat_is_ratio = importance_sampling_ratio * mask
    else:
        delta = torch.tensor([]).detach()
        flat_is_ratio = torch.tensor([]).detach()
    if beta != 0.0:
        loss_i = loss_i + beta * kl_i

    mask = mask.to(torch.float32)
    n_mask_per_reward = mask.sum(1)

    # https://github.com/huggingface/trl/blob/e8b8499f1f8d76838155b515e414ee98f757d6d5/trl/trainer/grpo_trainer.py#L1624
    if loss_type in ["grpo", "sapo"]:
        loss = ((loss_i * mask).sum(-1) / mask.sum(-1).clamp(min=1.0)).mean()
        loss = loss / current_gradient_accumulation_steps
    elif loss_type == "bnpo":
        loss = (loss_i * mask).sum() / mask.sum().clamp(min=1.0)
        loss = loss / current_gradient_accumulation_steps
    elif loss_type == "dr_grpo":
        loss = (loss_i * mask).sum() / (loss_i.size(0) * max_completion_length)
        loss = loss / current_gradient_accumulation_steps
    elif loss_type in ["cispo", "dapo", "vespo"]:
        normalizer = num_items_in_batch/ num_processes
        loss = (loss_i * mask).sum() / normalizer
    elif loss_type == "luspo":
        loss = (loss_i * mask.sum(1, keepdim=True)).mean()
        normalizer = current_gradient_accumulation_steps
        loss = loss / normalizer
    else:
        raise ValueError(f"Unknown loss type: {loss_type}")

    # Folded metrics.
    def masked_batch_mean(x):
        with torch.inference_mode():
            completion_length = n_mask_per_reward.mean()
            if x.shape[1] == 1:  # when importance_sampling_level == "sequence"
                return completion_length, x.mean()
            else:
                mean_kl_per_reward = (x * mask).sum(1) / n_mask_per_reward
                mean_kl = mean_kl_per_reward.mean()
                return completion_length, mean_kl
    completion_length, mean_kl = masked_batch_mean(kl_i)
    return loss, completion_length, mean_kl, delta, flat_is_ratio, coef_1, mask

class UnslothEfficientGRPO(torch.autograd.Function):
    # All Unsloth Zoo code licensed under AGPL3
    @staticmethod
    def forward(ctx, _new_logps, _old_logps, _ref_logps, _sampling_per_token_logps, lm_head, _input_ids, _mask, _advantages, beta, scaler = None, n_chunks = 1, extra_kwargs=None):
        if extra_kwargs is None:
            extra_kwargs = {}
        def compute_loss(new_logps, old_logps, ref_logps, sampling_per_token_logps, input_ids, mask, advantages, scaling):
            loss, completion_length, mean_kl, delta, flat_is_ratio, coef_1, _mask  = grpo_compute_loss(
                ref_logps,
                new_logps,
                old_logps,
                sampling_per_token_logps,
                input_ids,
                mask,
                beta,
                advantages,
                **extra_kwargs,
            )

            # Scale for mixed precision; return loss.detach() or autograd uses 2x VRAM.
            scaled_loss = loss * scaling
            return scaled_loss, (loss.detach(), completion_length, mean_kl, delta, flat_is_ratio, coef_1)
        pass

        device =_new_logps.device
        grad_inputs = torch.empty_like(_new_logps)
        accumulated_loss              = torch.zeros(1, device = device)[0]
        accumulated_completion_length = torch.zeros(1, device = device)[0]
        accumulated_mean_kl           = torch.zeros(1, device = device)[0]
        accumulated_delta             = []
        accumulated_flat_is_ratio     = []
        accumulated_coef_1            = []

        def accumulate_chunk(
            new_logps_j,
            old_logps_j,
            ref_logps_j,
            sampling_per_token_logps_j,
            input_ids_j,
            mask_j,
            advantages_j,
            scaling,
            grad_inputs_j,
        ):
            (chunk_grad_input,), (chunk_loss, (unscaled_loss, chunk_completion_length, chunk_mean_kl, chunk_delta, chunk_flat_is_ratio, chunk_coef_1)) = torch.func.grad_and_value(
                compute_loss,
                argnums = (0,),
                has_aux = True,
            )(new_logps_j, old_logps_j, ref_logps_j, sampling_per_token_logps_j, input_ids_j, mask_j, advantages_j, scaling)
            accumulated_loss             .add_(unscaled_loss)
            accumulated_completion_length.add_(chunk_completion_length)
            accumulated_mean_kl          .add_(chunk_mean_kl)
            accumulated_delta            .append(chunk_delta)
            accumulated_flat_is_ratio    .append(chunk_flat_is_ratio)
            accumulated_coef_1           .append(chunk_coef_1)
            grad_inputs_j[:] = chunk_grad_input
        pass

        from unsloth_zoo.temporary_patches.utils import torch_compile_with_fallback
        accumulate_chunk = torch_compile_with_fallback(
            fullgraph = True,
            # [TODO] Dynamic marking causes torch.compile errors if sequence length is long
            dynamic = True,
            options = torch_compile_options,
        )(accumulate_chunk)

        grad_inputs_chunks = torch.chunk(grad_inputs,        chunks = n_chunks, dim = 0)
        new_logps  = torch.chunk(_new_logps, chunks = n_chunks, dim = 0)
        if _old_logps is not None:
            old_logps  = torch.chunk(_old_logps, chunks = n_chunks, dim = 0)
        else:
            old_logps = [None] * n_chunks
        if _ref_logps is not None:
            ref_logps  = torch.chunk(_ref_logps, chunks = n_chunks, dim = 0)
        else:
            ref_logps = [None] * n_chunks
        if _sampling_per_token_logps is not None:
            sampling_per_token_logps  = torch.chunk(_sampling_per_token_logps, chunks = n_chunks, dim = 0)
        else:
            sampling_per_token_logps = [None] * n_chunks
        input_ids          = torch.chunk(_input_ids,         chunks = n_chunks, dim = 0)
        mask               = torch.chunk(_mask,              chunks = n_chunks, dim = 0)
        advantages         = torch.chunk(_advantages,        chunks = n_chunks, dim = 0)

        # Mixed precision scaling if present.
        scaling = scaler.get_scale() if scaler is not None else 1.0

        for (grad_inputs_j, new_logps_j, old_logps_j, ref_logps_j, sampling_per_token_logps_j, input_ids_j, mask_j, advantages_j, ) in \
            zip(grad_inputs_chunks, new_logps, old_logps, ref_logps, sampling_per_token_logps, input_ids, mask, advantages):

            # [TODO] Dynamic marking causes torch.compile errors if sequence length is long

            # mark_dynamic(new_hidden_states_j)
            # mark_dynamic(ref_hidden_states_j)
            # if old_hidden_states_j is not None:
            #     mark_dynamic(old_hidden_states_j)
            # mark_dynamic(input_ids_j)
            # mark_dynamic(mask_j)
            accumulate_chunk(
                new_logps_j,
                old_logps_j,
                ref_logps_j,
                sampling_per_token_logps_j,
                input_ids_j,
                mask_j,
                advantages_j,
                scaling,
                grad_inputs_j,
            )
        pass

        grad_inputs                  .div_(n_chunks)
        accumulated_loss             .div_(n_chunks)
        accumulated_completion_length.div_(n_chunks)
        accumulated_mean_kl          .div_(n_chunks)

        if _sampling_per_token_logps is not None:
            accumulated_delta = torch.cat(accumulated_delta, dim=0)
            accumulated_flat_is_ratio = torch.cat(accumulated_flat_is_ratio, dim=0)
        else:
            accumulated_delta = None
            accumulated_flat_is_ratio = None
        accumulated_coef_1  = torch.cat(accumulated_coef_1, dim=0)
        ctx.save_for_backward(grad_inputs)
        return (
            accumulated_loss,
            accumulated_completion_length,
            accumulated_mean_kl,
            accumulated_delta,
            accumulated_flat_is_ratio,
            accumulated_coef_1
        )
    pass

    @staticmethod
    def backward(ctx, grad_output, dcompletion_length, dmean_kl, ddelta, ddflat_is_ratio, dcoef_1):
        (grad_input,) = ctx.saved_tensors
        return (grad_input, None, None, None, None, None, None, None, None, None, None, None)
    pass

def grpo_accumulated_loss(
    trainer,
    input_ids,
    attention_mask,
    logits_to_keep,
    completion_mask,
    advantages,
    old_logps,
    ref_logps,
    n_chunks = -1,
    tool_mask = None,
    **kwargs,
):
    # All Unsloth Zoo code licensed under AGPL3
    bsz, qlen = input_ids.shape

    pixel_values = kwargs.get('pixel_values',None)
    image_grid_thw = kwargs.get('image_grid_thw',None)
    pixel_attention_mask = kwargs.get('pixel_attention_mask',None)
    image_sizes = kwargs.get('image_sizes',None)
    num_images = kwargs.get('num_images',None)
    # Transformers 5.x requires token_type_ids/mm_token_type_ids for some vision models
    token_type_ids = kwargs.get('token_type_ids',None)
    mm_token_type_ids = kwargs.get('mm_token_type_ids',None)
    if mm_token_type_ids is not None or image_grid_thw is not None:
        mm_token_type_ids = _unsloth_fix_mm_token_type_ids(
            trainer.processing_class, input_ids, mm_token_type_ids
        )
    sampling_per_token_logps = kwargs.get("sampling_per_token_logps", None) if getattr(trainer, "vllm_importance_sampling_correction", False) else None
    temperature = kwargs.get("temperature", 1.0)
    logit_scale_multiply = kwargs.get("logit_scale_multiply", 0.0)
    logit_scale_divide   = kwargs.get("logit_scale_divide", 0.0)
    logit_softcapping    = kwargs.get("logit_softcapping", 0.0)
    prev_max_left_pad    = kwargs.get("max_left_pad", 0) # max_left_pad for LLM training, enabled by default.

    # Pop from kwargs to avoid downstream issues.
    _ = kwargs.pop("sampling_per_token_logps", None)
    kwargs["vllm_importance_sampling_cap"] = getattr(trainer.args, "vllm_importance_sampling_cap", None)
    # Older TRL lacks this arg; fall back to token_truncate (legacy clamp(max=cap) behavior).
    kwargs["vllm_importance_sampling_mode"] = getattr(trainer.args, "vllm_importance_sampling_mode", None) or "token_truncate"
    kwargs["vllm_importance_sampling_clip_min"] = getattr(trainer.args, "vllm_importance_sampling_clip_min", None)
    kwargs["vllm_importance_sampling_clip_max"] = getattr(trainer.args, "vllm_importance_sampling_clip_max", None)
    kwargs["get_sapo_token_loss"] = trainer.get_sapo_token_loss if hasattr(trainer, "get_sapo_token_loss") else None
    kwargs["sapo_temperature_pos"] = trainer.args.sapo_temperature_pos if hasattr(trainer.args, "sapo_temperature_pos") else None
    kwargs["sapo_temperature_neg"] = trainer.args.sapo_temperature_neg if hasattr(trainer.args, "sapo_temperature_neg") else None
    kwargs["get_gamma_weights"] = trainer.get_gamma_weights if hasattr(trainer, "get_gamma_weights") else None
    kwargs["vespo_k_pos"] = trainer.args.vespo_k_pos if hasattr(trainer.args, "vespo_k_pos") else 2.0
    kwargs["vespo_k_neg"] = trainer.args.vespo_k_neg if hasattr(trainer.args, "vespo_k_neg") else 3.0
    kwargs["vespo_lambda_pos"] = trainer.args.vespo_lambda_pos if hasattr(trainer.args, "vespo_lambda_pos") else 3.0
    kwargs["vespo_lambda_neg"] = trainer.args.vespo_lambda_neg if hasattr(trainer.args, "vespo_lambda_neg") else 2.0
    kwargs["get_off_policy_mask"] = trainer.get_off_policy_mask if hasattr(trainer, "get_off_policy_mask") else None
    kwargs["off_policy_mask_threshold"] = trainer.args.off_policy_mask_threshold  if hasattr(trainer.args, "off_policy_mask_threshold") else None
    kwargs["use_vllm"] = trainer.use_vllm
    # Snap n_chunks to the closest divisor of bsz.
    factors = [i for i in range(1, bsz + 1) if bsz % i == 0]
    if n_chunks == -1: n_chunks = bsz
    n_chunks = factors[min(np.searchsorted(factors, n_chunks), len(factors)-1)]

    if kwargs["vllm_importance_sampling_clip_max"] is None and kwargs["vllm_importance_sampling_cap"] is not None:
        kwargs["vllm_importance_sampling_clip_min"] = 0
        kwargs["vllm_importance_sampling_clip_max"] = kwargs["vllm_importance_sampling_cap"]

    if not hasattr(trainer, '_autocast_dtype'):
        trainer._autocast_dtype = torch.float16 if os.environ.get('ACCELERATE_MIXED_PRECISION', 'fp16') == 'fp16' else torch.bfloat16
        if os.environ.get('UNSLOTH_FORCE_FLOAT32', '0') == '1': trainer._autocast_dtype = None
    pass
    os.environ["UNSLOTH_RETURN_HIDDEN_STATES"] = "1"

    lm_head = trainer.model.get_output_embeddings().weight
    dtype_bytes = 16 if trainer._autocast_dtype in [torch.float16, torch.bfloat16] else 32

    total_rows = input_ids.shape[0]
    seq_len = input_ids.shape[1]
    hidden_dim = lm_head.shape[1]
    vocab_dim = lm_head.shape[0]

    if trainer.args.unsloth_grpo_mini_batch is None:
        if not hasattr(trainer, "_has_autotuned"):
            trainer._has_autotuned = True
            B, multiplier = autotune_batch_and_chunks(
                total_rows, seq_len, hidden_dim, vocab_dim, dtype_bytes, trainer.args.unsloth_logit_chunk_multiplier
            )
            trainer.args.unsloth_grpo_mini_batch = max(1, total_rows//B)
            trainer.args.unsloth_logit_chunk_multiplier = multiplier
            B = trainer.args.unsloth_grpo_mini_batch
            multiplier = trainer.args.unsloth_logit_chunk_multiplier
        elif trainer._step % trainer.current_gradient_accumulation_steps == 0:
            B = trainer.args.unsloth_grpo_mini_batch
            multiplier = trainer.args.unsloth_logit_chunk_multiplier
            del trainer._has_autotuned
            del trainer.args.unsloth_grpo_mini_batch
            del trainer.args.unsloth_logit_chunk_multiplier
        else:
            B = trainer.unsloth_grpo_mini_batch
            multiplier = trainer.args.unsloth_logit_chunk_multiplier
    else:
        if trainer.args.unsloth_grpo_mini_batch > total_rows:
            B = total_rows
        else:
            B = trainer.args.unsloth_grpo_mini_batch

        if trainer.args.unsloth_logit_chunk_multiplier is None:
            multiplier = max(4, seq_len // 4096)
        else:
            multiplier = trainer.args.unsloth_logit_chunk_multiplier

    if pixel_values is None:
        left_pad_tokens_per_prompt = calculate_pad_tokens_in_prompt(input_ids, logits_to_keep, trainer.processing_class.pad_token_id)

        # Determine max_left_pad from precomputed logprobs shape for consistency
        if old_logps is not None:
            max_left_pad = old_logps.shape[1] - logits_to_keep
        elif ref_logps is not None:
            max_left_pad = ref_logps.shape[1] - logits_to_keep
        else:
            max_left_pad = torch.max(left_pad_tokens_per_prompt).item()

        input_ids = left_pack_padding(input_ids, trainer.processing_class.pad_token_id)

        completion_input_ids = input_ids[:, -(logits_to_keep +max_left_pad):]
        completion_mask = create_completion_attention_mask(completion_input_ids, left_pad_tokens_per_prompt, max_left_pad, trainer.processing_class.pad_token_id).to(attention_mask.dtype)

        if trainer.use_vllm and sampling_per_token_logps is not None and getattr(trainer, "vllm_importance_sampling_correction", False):
            sampling_per_token_logps = align_logprobs_with_mask(sampling_per_token_logps, completion_mask)
        else:
            sampling_per_token_logps = None
        completion_mask = align_completion_tool_mask(tool_mask, completion_mask)
        attention_mask =  input_ids != trainer.processing_class.pad_token_id
        attention_mask = attention_mask.to(attention_mask.dtype)
    else:
        completion_input_ids = input_ids[:, -logits_to_keep:]
        completion_mask = align_completion_tool_mask(tool_mask, completion_mask)

    unwrapped_model = trainer.accelerator.unwrap_model(trainer.model, keep_fp32_wrapper = False)

    for module in unwrapped_model.modules():
        if hasattr(module, "_hf_hook") and hasattr(module._hf_hook, "io_same_decice"):
            module._hf_hook.io_same_decice = False
    pass

    all_logprobs_list = []

    def slice_sample_axis(value, start, end):
        if value is None:
            return None
        return value[start:end]

    import math
    total_samples = input_ids.shape[0]
    batch_size = math.ceil(total_samples / B)
    if isinstance(num_images, torch.Tensor):
        num_images = num_images.detach().cpu().reshape(-1).tolist()
    if image_grid_thw is not None and pixel_values is not None and num_images is not None:
        rows_per_image = image_grid_thw.prod(dim=-1)
        rows_per_sample = torch.split(rows_per_image, num_images)
        rows_per_sample = torch.stack([s.sum() for s in rows_per_sample])
        cum_rows = torch.cat(
            [
                torch.tensor([0], device=rows_per_sample.device),
                rows_per_sample.cumsum(0),
            ]
        )
        cum_imgs = torch.tensor([0] + num_images).cumsum(0)
    else:
        cum_rows = None
        cum_imgs = None

    input_ids_chunks = []
    attention_mask_chunks = []
    completion_ids_chunks = []
    pixel_values_chunks = []
    image_grid_thw_chunks = []
    pixel_attention_mask_chunks = []
    image_sizes_chunks = []
    token_type_ids_chunks = []
    mm_token_type_ids_chunks = []

    current_pixel_idx = 0
    #TRL 0.23.0 batching logic
    for start in range(0, total_samples, batch_size):
        end = min(start + batch_size, total_samples)

        input_ids_chunks.append(input_ids[start:end])
        attention_mask_chunks.append(attention_mask[start:end])
        completion_ids_chunks.append(completion_input_ids[start:end])
        image_sizes_chunks.append(slice_sample_axis(image_sizes, start, end))
        token_type_ids_chunks.append(slice_sample_axis(token_type_ids, start, end))
        mm_token_type_ids_chunks.append(
            slice_sample_axis(mm_token_type_ids, start, end)
        )

        if image_grid_thw is not None and pixel_values is not None:

            if num_images is None:
                grid_slice = image_grid_thw[start:end]
                batch_pixel_count = grid_slice.prod(dim=-1).sum().item()
                start_pixel_idx = current_pixel_idx
                end_pixel_idx = current_pixel_idx + batch_pixel_count
                current_pixel_idx = end_pixel_idx
            else:
                start_pixel_idx = cum_rows[start].item()
                end_pixel_idx = cum_rows[end].item()
                img_start, img_end = cum_imgs[start], cum_imgs[end]
                grid_slice = image_grid_thw[img_start:img_end]
            image_grid_thw_chunks.append(grid_slice)

            pixel_values_chunks.append(pixel_values[start_pixel_idx:end_pixel_idx])

            if pixel_attention_mask is not None:
                if pixel_attention_mask.shape[0] == pixel_values.shape[0]:
                    pixel_attention_mask_chunks.append(pixel_attention_mask[start_pixel_idx:end_pixel_idx])
                else:
                    pixel_attention_mask_chunks.append(pixel_attention_mask[start:end])
            else:
                pixel_attention_mask_chunks.append(None)

        else:
            pixel_values_chunks.append(None)
            image_grid_thw_chunks.append(None)
            pixel_attention_mask_chunks.append(None)

    zipped_inputs = zip(
        input_ids_chunks,
        attention_mask_chunks,
        pixel_values_chunks,
        image_grid_thw_chunks,
        pixel_attention_mask_chunks,
        image_sizes_chunks,
        token_type_ids_chunks,
        mm_token_type_ids_chunks,
        completion_ids_chunks
    )

    if trainer._autocast_dtype is None:
        autocaster = nullcontext()
    else:
        autocaster = torch.amp.autocast(device_type = trainer.model.device.type, dtype = trainer._autocast_dtype)

    # PrefixGrouper grad path. This function's source is copied into the generated
    # UnslothGRPOTrainer cache without unsloth_zoo's module imports, so bind names
    # inside the body; the prefix_grouper import stays lazy + guarded (circular import,
    # may be absent) and a failed import just leaves PG off.
    from unsloth_zoo.temporary_patches.common import UNSLOTH_ENABLE_LOGGING

    # Memoize env gate + import once per process on the function object (which survives
    # into the cache). Env gate checked first so =0 never imports PG code; () = PG off.
    _pg_funcs = getattr(grpo_accumulated_loss, "_pg_funcs", None)
    if _pg_funcs is None:
        _pg_funcs = ()
        if os.environ.get("UNSLOTH_GRPO_PREFIX_GROUPER", "1").lower() not in (
            "0", "false", "no", "off",
        ):
            try:
                from unsloth.utils.prefix_grouper import (
                    build_group_layout as _pg_build_layout,
                    prefix_grouper_enabled as _pg_enabled_fn,
                    verify_on as _pg_verify_on,
                    tol_ok as _pg_tol_ok,
                    TOL_KILL as _PG_TOL_KILL,
                )
                _pg_funcs = (
                    _pg_build_layout, _pg_enabled_fn, _pg_verify_on, _pg_tol_ok, _PG_TOL_KILL,
                )
            except Exception:
                _pg_funcs = ()
        grpo_accumulated_loss._pg_funcs = _pg_funcs
    # Skip PG under vLLM (fast_inference=True): rollout dominates the step, so the
    # saving is small and the first-use self-verify is net overhead.
    _pg_engage = bool(_pg_funcs) and not getattr(trainer, "use_vllm", False)

    # ---- PrefixGrouper (GRPO shared-prompt dedup; UNSLOTH_GRPO_PREFIX_GROUPER=0 disables) ----
    # Each prompt's G completions share the prefix; PG forwards it once + the G suffixes
    # (FlexAttention shared-prefix mask), cutting G*(P+R) tokens to P+G*R. First-use
    # self-verify vs the full-row packed new_logprobs; grads flow through the shared stream
    # (prefix grad once = sum of G repeats, identical math). Off/failed/unverified ->
    # full-row packed path runs as before.
    _pg_result = None
    _pg_use = False
    _pg_skip_pack = False
    _pg_num_gen = getattr(trainer, "num_generations", None)
    # Runtime gate; broad except -> engage False.
    if _pg_engage and _pg_funcs:
        try:
            _pg_build_layout, _pg_enabled_fn, _pg_verify_on, _pg_tol_ok, _PG_TOL_KILL = _pg_funcs
            # Exclusions: softcap models (gemma2) - the FlexAttention kernel skips
            # attn_logit_softcapping; hybrid SSM (FalconH1) and MoE (Qwen3-MoE) - their
            # decoders do not thread prefix_seg_info, so state would leak across suffixes.
            _pg_cfg = getattr(unwrapped_model, "config", None)
            _pg_engage = (
                _pg_enabled_fn()
                and pixel_values is None
                and token_type_ids is None
                and mm_token_type_ids is None
                and _pg_num_gen is not None
                and _pg_num_gen >= 2
                and not getattr(_pg_cfg, "attn_logit_softcapping", None)
                and not any(
                    getattr(_pg_cfg, _pg_a, None) is not None
                    for _pg_a in ("mamba_d_ssm", "mamba_d_state", "mamba_expand")
                )
                and not any(
                    getattr(_pg_cfg, _pg_a, None) is not None
                    for _pg_a in (
                        "num_experts", "num_experts_per_tok", "num_local_experts",
                        "n_routed_experts", "moe_intermediate_size",
                    )
                )
            )
        except Exception:
            _pg_engage = False
    else:
        _pg_engage = False
    _pg_layout = None
    _pg_trusted = False   # signature already verified -> skip the full-row forward this step
    if _pg_engage:
        try:
            _pg_pad_id = trainer.processing_class.pad_token_id
            # Build the layout from the left-packed input_ids with the original left-pad
            # counts so the prefix/suffix split matches the packed path (_pack_cstart) and
            # the verify is apples-to-apples. Cap the PG span at any sliding window,
            # mirroring the packed _pack_sw guard.
            _pg_sw = getattr(getattr(unwrapped_model, "config", None), "sliding_window", None)
            if not (isinstance(_pg_sw, int) and _pg_sw > 0):
                _pg_sw = None
            _pg_layout = _pg_build_layout(
                input_ids, logits_to_keep, _pg_pad_id, _pg_num_gen, left_pad_tokens_per_prompt,
                max_segment_cap = _pg_sw,
            )
            _pg_unsafe = getattr(unwrapped_model, "_unsloth_prefix_grouper_grad_unsafe", None)
            if _pg_unsafe is None:
                _pg_unsafe = set()
            if _pg_layout is not None and _pg_layout.signature in _pg_unsafe:
                _pg_layout = None
            elif _pg_layout is not None:
                _pg_layout.W = logits_to_keep + max_left_pad
                _pg_verified = getattr(unwrapped_model, "_unsloth_prefix_grouper_grad_verified", None)
                # trust only if the verified envelope covers this batch's lengths
                # (re-verify when T or the longest segment grows)
                _pg_T = int(_pg_layout.flat_ids.shape[1])
                _pg_maxseg = int(_pg_layout.position_ids.max()) + 1
                _pg_env = (
                    _pg_verified.get(_pg_layout.signature)
                    if isinstance(_pg_verified, dict) else None
                )
                if (not _pg_verify_on()) or (
                    _pg_env is not None and _pg_T <= _pg_env[0] and _pg_maxseg <= _pg_env[1]
                ):
                    _pg_trusted = True
                    _pg_skip_pack = True   # trusted shape -> skip the full-row forward
        except Exception as _pg_err:
            _pg_layout = None
            _pg_trusted = False
            _pg_skip_pack = False
            if isinstance(_pg_err, torch.cuda.OutOfMemoryError):
                torch.cuda.empty_cache()
            os.environ["UNSLOTH_RETURN_HIDDEN_STATES"] = "1"
            if UNSLOTH_ENABLE_LOGGING:
                print(f"[Unsloth] GRPO PrefixGrouper (grad) disabled (fell back to packed): {_pg_err!r}", flush = True)

    # ---- Sequence packing (default-on; disable with UNSLOTH_GRPO_SEQ_PACKING=0) ----
    # One varlen [1, sum L] block-diagonal forward replaces the padded [B, Lmax] loop: the exact per-row
    # result, and it fixes the padded path's left-pad RoPE error. Loss/gradients flow through it. Self-
    # verified against the per-row forward (shape/RoPE-aware, re-checked as T grows); falls back if a
    # backend ignores packed_seq_lengths. lm_head runs on completion positions only.
    new_logprobs = None
    _pack_result = None
    _pack_use = False
    _pack_enabled = os.environ.get("UNSLOTH_GRPO_SEQ_PACKING", "1").lower() not in ("0", "false", "no", "off")
    _pack_ok = getattr(unwrapped_model, "_unsloth_seq_packing_grad_ok", None)
    if (_pack_enabled and not _pg_skip_pack and pixel_values is None
            and token_type_ids is None and mm_token_type_ids is None and _pack_ok is not False):
        try:
            _pack_pad_id = trainer.processing_class.pad_token_id
            _pack_keep = input_ids != _pack_pad_id
            _pack_lengths = _pack_keep.sum(dim = 1)
            _pack_lengths_cpu = _pack_lengths.tolist()                 # single GPU->CPU sync, reused below
            _pack_nz_cpu = [_n for _n in _pack_lengths_cpu if _n > 0]
            _pack_flat_ids = input_ids[_pack_keep].unsqueeze(0)
            _pack_T = _pack_flat_ids.shape[1]
            _pack_L = input_ids.shape[1]
            _pack_W = logits_to_keep + max_left_pad
            _pack_maxseg = max(_pack_nz_cpu) if _pack_nz_cpu else 0
            # sliding-window models lose the per-sequence local window in a packed stream
            _pack_sw = getattr(getattr(unwrapped_model, "config", None), "sliding_window", None)
            _pack_sw_ok = not (isinstance(_pack_sw, int) and _pack_sw > 0 and _pack_maxseg > _pack_sw)
            _pack_active = int((completion_mask.sum(dim = 1) > 0).sum())
            _pack_unsafe = getattr(unwrapped_model, "_unsloth_seq_packing_grad_unsafe_T", None)
            # skip the whole packed forward for a known-unsafe length region (a prior moderate mismatch)
            if _pack_T >= 2 and len(_pack_nz_cpu) > 0 and _pack_sw_ok and (_pack_ok is True or _pack_active >= 2) \
                    and not (_pack_unsafe is not None and _pack_T >= _pack_unsafe):
                _pack_psl = torch.tensor(_pack_nz_cpu, dtype = torch.int32, device = input_ids.device)
                # reset 0-based position_ids per segment
                _pack_pos = (_pack_keep.cumsum(dim = 1) - 1)[_pack_keep].unsqueeze(0)
                _pack_chunks = max(1, total_rows * multiplier)
                _pack_nz_idx = _pack_keep.nonzero(as_tuple = False)            # [T, 2] = (row, col)
                _pack_within = _pack_nz_idx[1:, 0] == _pack_nz_idx[:-1, 0]     # [T-1]
                # completion start is per-row after left-packing: (L - logits_to_keep) minus that
                # row's left-pad (matches create_completion_attention_mask exactly)
                _pack_cstart = (_pack_L - logits_to_keep) - left_pad_tokens_per_prompt  # [rows]
                _pack_ctgt = (_pack_nz_idx[1:, 1] >= _pack_cstart[_pack_nz_idx[1:, 0]]) & _pack_within
                with autocaster:
                    # use_cache=False: a KV cache silently disables varlen packing
                    _pack_hidden = unwrapped_model(
                        input_ids = _pack_flat_ids,
                        position_ids = _pack_pos,
                        packed_seq_lengths = _pack_psl,
                        use_cache = False,
                    ).logits
                    # `.logits` carries hidden states only when the forward is the
                    # Unsloth generated one honouring UNSLOTH_RETURN_HIDDEN_STATES;
                    # otherwise it is real [T, vocab] logits and the lm_head matmul
                    # dies. Dispatch on width, as the padded path already does.
                    _pack_h   = _pack_hidden[0, :-1, :][_pack_ctgt].unsqueeze(0)
                    _pack_tid = _pack_flat_ids[0, 1:][_pack_ctgt].unsqueeze(0)
                    if _unsloth_grpo_returns_hidden_states(unwrapped_model, _pack_h, lm_head):
                        _pack_sel = chunked_hidden_states_selective_log_softmax(
                            _pack_h, lm_head, _pack_tid, _pack_chunks,
                            logit_scale_multiply, logit_scale_divide, logit_softcapping, temperature,
                        )[0]
                    else:
                        # Raw logits: the forward already applied scale/softcap.
                        _pack_sel = chunked_selective_log_softmax(
                            _pack_h, _pack_tid,
                            temperature = temperature, chunks = _pack_chunks,
                        )[0]
                # GPT-OSS offload race guard (matches the padded loop)
                device_synchronize()
                # scatter each completion logprob back to its (row, col) so [:, -_pack_W:] matches padded
                _pack_tgt = (_pack_nz_idx[1:, 0] * _pack_L + _pack_nz_idx[1:, 1])[_pack_ctgt]
                _pack_result = torch.zeros(
                    total_rows * _pack_L, dtype = torch.float32, device = input_ids.device,
                ).index_put((_pack_tgt,), _pack_sel.to(torch.float32)).view(total_rows, _pack_L)[:, -_pack_W:]
                # trust decision: re-verify when T or the longest segment grows past what was verified
                # (a LongRoPE cache switch can change the result)
                _pack_vT = int(getattr(unwrapped_model, "_unsloth_seq_packing_grad_verified_T", 0))
                _pack_vS = int(getattr(unwrapped_model, "_unsloth_seq_packing_grad_verified_seg", 0))
                _pack_force_verify = os.environ.get("UNSLOTH_GRPO_SEQ_PACKING_VERIFY", "0") == "1"
                if (not _pack_force_verify) and _pack_ok is True and _pack_T <= _pack_vT and _pack_maxseg <= _pack_vS:
                    _pack_use = True                                           # already verified for this shape
                else:
                    # verify against the per-row clean forward (exact ground truth; no grad, value check)
                    _pack_ref = torch.zeros_like(_pack_result)
                    with torch.no_grad(), autocaster:
                        for _pack_i in range(total_rows):
                            _pack_ni = _pack_lengths_cpu[_pack_i]
                            if _pack_ni < 2: continue
                            _pack_rmask = _pack_keep[_pack_i]
                            _pack_real = input_ids[_pack_i][_pack_rmask].unsqueeze(0)
                            _pack_rpos = torch.arange(_pack_ni, device = input_ids.device).unsqueeze(0)
                            _pack_rh = unwrapped_model(input_ids = _pack_real, position_ids = _pack_rpos, use_cache = False).logits
                            # same width dispatch as the packed call above: this forward
                            # returns raw logits whenever that one did, and the first
                            # packed batch always lands here
                            if _unsloth_grpo_returns_hidden_states(unwrapped_model, _pack_rh, lm_head):
                                _pack_rsel = chunked_hidden_states_selective_log_softmax(
                                    _pack_rh[:, :-1, :], lm_head, _pack_real[:, 1:], 1,
                                    logit_scale_multiply, logit_scale_divide, logit_softcapping, temperature,
                                )[0]
                            else:
                                _pack_rsel = chunked_selective_log_softmax(
                                    _pack_rh[:, :-1, :], _pack_real[:, 1:],
                                    temperature = temperature, chunks = 1,
                                )[0]
                            _pack_rcols = _pack_rmask.nonzero(as_tuple = False).squeeze(1)[1:] - (_pack_L - _pack_W)
                            _pack_rkeep = _pack_rcols >= 0
                            _pack_ref[_pack_i, _pack_rcols[_pack_rkeep]] = _pack_rsel[_pack_rkeep].to(torch.float32)
                    device_synchronize()
                    # compare over the exact loss-mask region (same mask the loss uses; pure
                    # create_completion_attention_mask, before any tool_mask is applied)
                    _pack_cm = create_completion_attention_mask(
                        input_ids[:, -_pack_W:], left_pad_tokens_per_prompt, max_left_pad, _pack_pad_id
                    ).float()
                    _pack_diff = float(((_pack_result.detach() - _pack_ref).abs() * _pack_cm).max())
                    if UNSLOTH_ENABLE_LOGGING:
                        print(f"[Unsloth] GRPO seq-packing (grad) verify: T={_pack_T} maxseg={_pack_maxseg} packed-vs-perrow max|d|={_pack_diff:.4f}", flush = True)
                    # floor ~0.25 through different kernels; cross-sample contamination is >= 2.4
                    if _pack_diff < 7e-1:
                        unwrapped_model._unsloth_seq_packing_grad_ok = True
                        # only widen the trusted shape when >= 2 completion rows actually exercised
                        # cross-sample packing; a < 2 row pass proves nothing, so keep re-verifying
                        # larger shapes until a real multi-row batch clears them
                        if _pack_active >= 2:
                            unwrapped_model._unsloth_seq_packing_grad_verified_T = max(_pack_vT, _pack_T)
                            unwrapped_model._unsloth_seq_packing_grad_verified_seg = max(_pack_vS, _pack_maxseg)
                        _pack_ok = True
                        _pack_use = True
                    else:
                        _pack_use = False
                        if _pack_diff >= 1.5:
                            # large mismatch = contamination (attention ignores the packed mask, e.g.
                            # some MoE): disable packing for this model
                            unwrapped_model._unsloth_seq_packing_grad_ok = False
                        else:
                            # moderate mismatch -> likely a length boundary (LongRoPE): mark unsafe but
                            # keep packing for smaller shapes
                            unwrapped_model._unsloth_seq_packing_grad_unsafe_T = (
                                _pack_T if _pack_unsafe is None else min(_pack_unsafe, _pack_T)
                            )
                        if UNSLOTH_ENABLE_LOGGING:
                            print(f"[Unsloth] GRPO seq-packing (grad) fell back at T={_pack_T} (diff={_pack_diff:.3f})", flush = True)
        except Exception as _pack_err:
            # any failure -> drop intermediates, use the padded loop, do not retry
            _pack_hidden = None
            _pack_sel = None
            _pack_result = None
            _pack_use = False
            if isinstance(_pack_err, torch.cuda.OutOfMemoryError):
                torch.cuda.empty_cache()
            unwrapped_model._unsloth_seq_packing_grad_ok = False
            if UNSLOTH_ENABLE_LOGGING:
                print(f"[Unsloth] GRPO sequence-packing disabled (fell back to padded): {_pack_err!r}", flush = True)
    # ---- PrefixGrouper resolution + first-use self-verify (grad) ----
    # Verify runs under no_grad, then a separate grad forward builds new_logprobs,
    # so no inference tensors are saved for backward.
    def _pg_grad_forward():
        _pg_chunks = max(1, total_rows * multiplier)
        with autocaster:
            _h = unwrapped_model(
                input_ids = _pg_layout.flat_ids,
                position_ids = _pg_layout.position_ids,
                prefix_seg_info = _pg_layout.prefix_seg_info,
                use_cache = False,
            ).logits
            # Same width dispatch as the packed path and compute_logprobs_chunk.
            # `.logits` carries hidden states only when the forward is the Unsloth
            # generated one honouring UNSLOTH_RETURN_HIDDEN_STATES; otherwise it is
            # real [T, vocab] logits. extract_logps always calls its helper as
            # (hidden, lm_head, ids, chunks, ...), so pass a raw-logits helper with
            # that same signature, which skips the lm_head matmul and the scale /
            # softcap the forward already applied.
            _pg_fn = chunked_hidden_states_selective_log_softmax
            if not _unsloth_grpo_returns_hidden_states(unwrapped_model, _h, lm_head):
                def _pg_fn(_pg_h, _pg_lm, _pg_ids, _pg_n, _pg_lsm, _pg_lsd, _pg_lsc, _pg_t):
                    return chunked_selective_log_softmax(
                        _pg_h, _pg_ids, temperature = _pg_t, chunks = _pg_n,
                    )
            _pg_lp = _pg_layout.extract_logps(
                _h, lm_head, _pg_fn,
                _pg_chunks, logit_scale_multiply, logit_scale_divide,
                logit_softcapping, temperature,
            )  # [total_rows, W] with grad
            # GPT-OSS offload race guard
            device_synchronize()
            return _pg_lp

    if _pg_layout is not None:
        # A verify-phase OOM (packed graph co-resident) does not prove PG alone cannot fit;
        # only an OOM after the packed graph is freed is worth marking unsafe.
        _pg_phase_verify = False
        try:
            if not _pg_trusted:
                # first use: verify vs the packed new_logprobs. < tol_ok -> trust;
                # >= TOL_KILL -> unsafe forever; borderline -> fall back this shape.
                if _pack_use and _pack_result is not None:
                    _pg_phase_verify = True   # packed graph still co-resident
                    with torch.no_grad():
                        _pg_ref = _pg_grad_forward()
                    _pg_W2 = logits_to_keep + max_left_pad
                    _pg_cm = create_completion_attention_mask(
                        input_ids[:, -_pg_W2:], left_pad_tokens_per_prompt, max_left_pad,
                        trainer.processing_class.pad_token_id,
                    ).float()
                    _pg_a = _pg_ref[:, -_pg_W2:].float()
                    _pg_b = _pack_result.detach()[:, -_pg_W2:].float()
                    _pg_diff = float(((_pg_a - _pg_b).abs() * _pg_cm).max())
                    if UNSLOTH_ENABLE_LOGGING:
                        print(
                            f"[Unsloth] GRPO PrefixGrouper (grad) verify: sig={_pg_layout.signature} "
                            f"shared-prefix vs full-row-packed max|d|={_pg_diff:.4f}", flush = True,
                        )
                    if _pg_diff < _pg_tol_ok():
                        _pg_v = getattr(unwrapped_model, "_unsloth_prefix_grouper_grad_verified", None)
                        if not isinstance(_pg_v, dict):
                            _pg_v = {}
                        _pg_vT = int(_pg_layout.flat_ids.shape[1])
                        _pg_vS = int(_pg_layout.position_ids.max()) + 1
                        _pg_old = _pg_v.get(_pg_layout.signature, (0, 0))
                        _pg_v[_pg_layout.signature] = (
                            max(_pg_vT, _pg_old[0]), max(_pg_vS, _pg_old[1]),
                        )
                        unwrapped_model._unsloth_prefix_grouper_grad_verified = _pg_v
                        _pg_trusted = True
                    else:
                        _pg_u = getattr(unwrapped_model, "_unsloth_prefix_grouper_grad_unsafe", None)
                        if _pg_u is None:
                            _pg_u = set()
                        if _pg_diff >= _PG_TOL_KILL:
                            _pg_u.add(_pg_layout.signature)
                            unwrapped_model._unsloth_prefix_grouper_grad_unsafe = _pg_u
                        _pg_trusted = False
                # else: no packed reference -> cannot verify -> fall back.
            if _pg_trusted:
                # free the packed graph BEFORE the grad forward: holding both can OOM when
                # PG alone would fit, and on PG failure the padded loop recomputes anyway.
                _pack_hidden = _pack_sel = _pack_result = None
                _pg_phase_verify = False   # packed freed: an OOM below is PG-alone
                _pg_result = _pg_grad_forward()
                _pg_use = True
        except Exception as _pg_err2:
            _pg_use = False
            os.environ["UNSLOTH_RETURN_HIDDEN_STATES"] = "1"
            # untrust this signature so the next batch runs the packed path again
            _pg_v = getattr(unwrapped_model, "_unsloth_prefix_grouper_grad_verified", None)
            if isinstance(_pg_v, dict):
                _pg_v.pop(_pg_layout.signature, None)
            if isinstance(_pg_err2, torch.cuda.OutOfMemoryError):
                # mark unsafe only for a PG-alone OOM (deterministic at these lengths);
                # a verify-phase OOM (packed co-resident) proves nothing, just retry.
                if not _pg_phase_verify:
                    _pg_u = getattr(unwrapped_model, "_unsloth_prefix_grouper_grad_unsafe", None)
                    if _pg_u is None:
                        _pg_u = set()
                    _pg_u.add(_pg_layout.signature)
                    unwrapped_model._unsloth_prefix_grouper_grad_unsafe = _pg_u
                torch.cuda.empty_cache()
            if UNSLOTH_ENABLE_LOGGING:
                print(f"[Unsloth] GRPO PrefixGrouper (grad) forward failed -> packed/padded fallback: {_pg_err2!r}", flush = True)

    if _pg_use and _pg_result is not None:
        new_logprobs = _pg_result            # PrefixGrouper verified -> skip the loop
        zipped_inputs = []
    elif _pack_use and _pack_result is not None:
        new_logprobs = _pack_result          # verified -> skip the loop
        zipped_inputs = []
    else:
        # packing rejected/unused: drop the packed graph before the padded loop so both don't co-reside
        _pack_hidden = _pack_sel = _pack_result = None

    def to_device(tensor, device, non_blocking=True):
        if tensor is None: return None
        return tensor.to(device, non_blocking=non_blocking)

    def _offload_device_module(tensor_or_device):
        # Stream/Event module for the offload copy. torch.cuda is also the HIP
        # backend, so ROCm reports is_cuda and needs no branch of its own; XPU has
        # its own namespace, matching gradient_checkpointing.py. Anything else
        # (CPU, MPS, ...) returns None and takes the pageable copy.
        device = getattr(tensor_or_device, "device", tensor_or_device)
        if device.type == "cuda": return torch.cuda
        if device.type == "xpu": return getattr(torch, "xpu", None)
        return None

    class Unsloth_Offloaded_Log_Softmax(torch.autograd.Function):
        """Manual gradient checkpointing / CPU offloading for log softmax."""
        @staticmethod
        def forward(ctx, hidden_states, lm_head, index, chunks,
                    logit_scale_multiply, logit_scale_divide,
                    logit_softcapping, temperature):
            # Detach so we don't keep the graph (and extra memory) on CPU.
            detached_hidden_states = hidden_states.detach().contiguous()
            ctx.device = hidden_states.device
            ctx.copy_event = None

            # Always offload: this path only runs when the caller is already memory bound
            # (long completions / large batches), so the win is overlapping the copy.
            saved_hidden_states = None
            device_module = _offload_device_module(detached_hidden_states)
            if device_module is not None:
                # Async D2H on a side stream; backward MUST wait on copy_event before
                # the H2D reload or it races the copy.
                try:
                    pinned_buffer = torch.empty_like(detached_hidden_states, device = "cpu", pin_memory = True)
                    if pinned_buffer is not None:
                        current_stream = device_module.current_stream(detached_hidden_states.device)
                        copy_stream = device_module.Stream(device = detached_hidden_states.device)
                        copy_stream.wait_stream(current_stream)
                        with device_module.stream(copy_stream):
                            pinned_buffer.copy_(detached_hidden_states, non_blocking = True)
                        # Keeps the GPU storage alive until the side-stream copy finishes.
                        detached_hidden_states.record_stream(copy_stream)
                        copy_event = device_module.Event()
                        copy_event.record(copy_stream)
                        saved_hidden_states = pinned_buffer
                        ctx.copy_event = copy_event
                except (RuntimeError, OSError, AttributeError):
                    # Any accelerator that cannot do pinned side-stream copies falls
                    # back below; correctness never depends on this path.
                    saved_hidden_states = None
                    ctx.copy_event = None
            if saved_hidden_states is None:
                # No accelerator, or the async copy is unavailable: pageable copy.
                saved_hidden_states = detached_hidden_states.to("cpu", non_blocking = True)
            ctx.saved_hidden_states = saved_hidden_states
            # Drop the clone before the log-softmax below. hidden_states is usually a
            # [:, :-1, :] slice, so .contiguous() allocated a full copy; holding the
            # reference across the forward would keep it resident alongside the chunk
            # logits. record_stream still blocks reuse until the D2H lands, so the
            # allocator reclaims it mid-compute rather than at the end of forward.
            del detached_hidden_states

            ctx.lm_head = lm_head
            ctx.lm_head_requires_grad = lm_head.requires_grad
            ctx.index = index
            ctx.args = (chunks, logit_scale_multiply, logit_scale_divide, logit_softcapping, temperature)

            with torch.no_grad():
                output = chunked_hidden_states_selective_log_softmax(
                    hidden_states, lm_head, index, *ctx.args
                )

            return output

        @staticmethod
        def backward(ctx, grad_output):
            if ctx.copy_event is not None:
                # The offload copy must land before the H2D reload.
                device_module = _offload_device_module(ctx.device)
                ctx.copy_event.wait(device_module.current_stream(ctx.device))
            hidden_states = to_device(ctx.saved_hidden_states, ctx.device)
            hidden_states.requires_grad_(True)

            lm_head = ctx.lm_head
            if ctx.lm_head_requires_grad:
                # Recompute against a private leaf. A Tensor.register_hook on the real
                # lm_head fires for tensors named in autograd.grad's inputs, so reusing
                # it here would run a user's grad mask / scaler once on this local
                # gradient and again when the returned gradient reaches lm_head.
                lm_head = lm_head.detach().requires_grad_(True)
            index = ctx.index

            with torch.enable_grad():
                output = chunked_hidden_states_selective_log_softmax(
                    hidden_states, lm_head, index, *ctx.args
                )

            # autograd.grad, not backward: backward writes into leaf .grad, which the
            # outer AccumulateGrad would then double-count.
            grad_inputs = torch.autograd.grad(
                output,
                (hidden_states, lm_head) if ctx.lm_head_requires_grad else (hidden_states,),
                grad_output,
            )

            return (
                grad_inputs[0],
                grad_inputs[1] if ctx.lm_head_requires_grad else None,
                None,
                None,
                None,
                None,
                None,
                None,
            )

    def efficient_log_softmax(hidden_states, lm_head, index, chunks=32,
                            logit_scale_multiply=0.0, logit_scale_divide=0.0,
                            logit_softcapping=0.0, temperature=1, batch_size=8):
        if (index.shape[1] <= 1024 and batch_size <= 8) or batch_size==1:
            # Normal path is faster / saves a GB under these conditions.
            return chunked_hidden_states_selective_log_softmax(
                hidden_states,
                lm_head,
                index,
                chunks,
                logit_scale_multiply,
                logit_scale_divide,
                logit_softcapping,
                temperature
            )
        else:
            return Unsloth_Offloaded_Log_Softmax.apply(
                hidden_states, lm_head, index, chunks,
                logit_scale_multiply, logit_scale_divide,
                logit_softcapping, temperature
            )

    def compute_logprobs_chunk(new_hidden_states_chunk, completion_ids, input_ids_chunk):
        # Hidden states -> lm_head matmul path; raw logits -> skip matmul and
        # skip scale/softcap (model forward already applied them).
        chunks = input_ids_chunk.shape[0] * multiplier
        if _unsloth_grpo_returns_hidden_states(unwrapped_model, new_hidden_states_chunk, lm_head):
            return efficient_log_softmax(
                new_hidden_states_chunk,
                lm_head,
                completion_ids,
                chunks = chunks,
                logit_scale_multiply = logit_scale_multiply,
                logit_scale_divide = logit_scale_divide,
                logit_softcapping = logit_softcapping,
                temperature = temperature,
                batch_size = B,
            )
        return chunked_selective_log_softmax(
            new_hidden_states_chunk,
            completion_ids,
            temperature = temperature,
            chunks = chunks,
        )
    for (
        input_ids_chunk,
        attention_mask_chunk,
        pixel_values_chunk,
        image_grid_thw_chunk,
        pixel_attention_mask_chunk,
        image_sizes_chunk,
        token_type_ids_chunk,
        mm_token_type_ids_chunk,
        completion_ids
    ) in zipped_inputs:
            _extra_vision_kwargs = {}
            if token_type_ids_chunk is not None:
                _extra_vision_kwargs["token_type_ids"] = token_type_ids_chunk
            if mm_token_type_ids_chunk is not None:
                _extra_vision_kwargs["mm_token_type_ids"] = mm_token_type_ids_chunk
            with autocaster:
                if pixel_values is None:
                    new_hidden_states_chunk = unwrapped_model(
                        input_ids = input_ids_chunk,
                        attention_mask = attention_mask_chunk,
                        pixel_values = pixel_values_chunk,
                        image_grid_thw = image_grid_thw_chunk,
                        pixel_attention_mask = pixel_attention_mask_chunk,
                        image_sizes = image_sizes_chunk,
                        **_extra_vision_kwargs,
                    ).logits

                    new_hidden_states_chunk = new_hidden_states_chunk[:, -(logits_to_keep + max_left_pad + 1): , :]
                    new_hidden_states_chunk = new_hidden_states_chunk[:, :-1, :]
                    logprobs_chunk = compute_logprobs_chunk(new_hidden_states_chunk, completion_ids, input_ids_chunk)
                else:
                    new_hidden_states_chunk = unwrapped_model(
                        input_ids = input_ids_chunk,
                        attention_mask = attention_mask_chunk,
                        pixel_values = pixel_values_chunk,
                        image_grid_thw = image_grid_thw_chunk,
                        pixel_attention_mask = pixel_attention_mask_chunk,
                        image_sizes = image_sizes_chunk,
                        logits_to_keep = logits_to_keep + 1,
                        **_extra_vision_kwargs,
                    ).logits

                    new_hidden_states_chunk = new_hidden_states_chunk[:, :-1, :]
                    logprobs_chunk = compute_logprobs_chunk(new_hidden_states_chunk, completion_ids, input_ids_chunk)
                # Avoids race conditions with GPT OSS offload_embbed=True; no measurable slowdown.
                device_synchronize()
            all_logprobs_list.append(logprobs_chunk)

    if new_logprobs is None:
        # padded fallback (packing disabled / unsupported / not verified for this length)
        new_logprobs = torch.cat(all_logprobs_list, dim=0)

    with autocaster:
        loss, completion_length, mean_kl, delta, flat_is_ratio, coef_1 = UnslothEfficientGRPO.apply(
            new_logprobs,
            old_logps,
            ref_logps,
            sampling_per_token_logps,
            lm_head,
            completion_input_ids,
            completion_mask,
            advantages,
            trainer.beta,
            trainer.accelerator.scaler,
            1,
            kwargs
        )

    # Force logits (not hidden states) again or output is gibberish.
    os.environ["UNSLOTH_RETURN_HIDDEN_STATES"] = "0"

    return loss, completion_length, mean_kl, delta, flat_is_ratio, coef_1, completion_mask
    # Old non-efficient code path (dead).
    new_logits = torch.matmul(new_hidden_states, lm_head.t())
    new_logits = new_logits[:, :-1, :] # exclude the last logit: it corresponds to the next token pred
    old_logits = torch.matmul(old_hidden_states, lm_head.t())
    old_logits = old_logits[:, :-1, :] # exclude the last logit: it corresponds to the next token pred
    loss, completion_length, mean_kl = grpo_compute_loss(
        old_logits,
        new_logits,
        completion_input_ids,
        completion_mask,
        trainer.beta,
        advantages,
    )
    return loss, completion_length, mean_kl
    pass

from unsloth_zoo.temporary_patches.utils import torch_compile_with_fallback
@torch_compile_with_fallback(dynamic = True, fullgraph = True, options = torch_compile_options)
def grpo_compute_loss_slow(
    ref,
    new,
    old,
    sampling_per_token_logps,
    input_ids,
    mask,
    beta,
    advantages,
    **kwargs
):
    # All Unsloth Zoo code licensed under AGPL3
    # Optional argument defaults.
    loss_type = kwargs.get("loss_type", "grpo")
    epsilon_low = kwargs.get("epsilon_low", 0.2)
    epsilon_high = kwargs.get("epsilon_high", 0.2)
    max_completion_length = kwargs.get("max_completion_length", 8192)
    delta = kwargs.get("delta", None)
    importance_sampling_level = kwargs.get("importance_sampling_level", "token")
    num_items_in_batch = kwargs.get("num_items_in_batch", None)
    current_gradient_accumulation_steps = kwargs.get("current_gradient_accumulation_steps", 1)
    num_processes = kwargs.get("num_processes", 1)
    use_vllm = kwargs.get("use_vllm", False)
    vllm_importance_sampling_mode = kwargs.get("vllm_importance_sampling_mode", "sequence_mask")
    vllm_importance_sampling_cap = kwargs.get("vllm_importance_sampling_cap", 2.0)
    vllm_importance_sampling_clip_min = kwargs.get("vllm_importance_sampling_clip_min", None)
    vllm_importance_sampling_clip_max = kwargs.get("vllm_importance_sampling_clip_max", 3.0)
    get_sapo_token_loss = kwargs.get("get_sapo_token_loss", None)
    sapo_temperature_pos = kwargs.get("sapo_temperature_pos", 1.0)
    sapo_temperature_neg = kwargs.get("sapo_temperature_neg", 1.05)
    get_gamma_weights = kwargs.get("get_gamma_weights", None)
    vespo_k_pos = kwargs.get("vespo_k_pos", 2.0)
    vespo_lambda_pos = kwargs.get("vespo_lambda_pos", 3.0)
    vespo_k_neg = kwargs.get("vespo_k_neg", 3.0)
    vespo_lambda_neg = kwargs.get("vespo_lambda_neg", 2.0)
    get_off_policy_mask = kwargs.get("get_off_policy_mask", None)
    off_policy_mask_threshold  = kwargs.get("off_policy_mask_threshold", None)
    input_ids = input_ids.unsqueeze(-1)

    importance_sampling_ratio = None

    # exp(new - old) and exp(ref - new) below are taken before `mask` is applied. A sequence-packed
    # logp path leaves the masked (prompt/pad) columns at 0 while a padded one fills them with a real
    # logp, so when new and old/ref disagree there those ratios can overflow to inf and inf * 0 (the
    # masked-out loss) becomes nan. Force new/old/ref to share 0 on the masked columns so both ratios
    # are exp(0) = 1 there; every loss term below multiplies by `mask`, so this changes nothing.
    if mask is not None:
        _keep = mask.to(torch.bool)
        new = torch.where(_keep, new, 0.0)
        if old is not None: old = torch.where(_keep, old, 0.0)
        if ref is not None: ref = torch.where(_keep, ref, 0.0)

    if advantages.dim() == 1:
        advantages = advantages.unsqueeze(1)

    if off_policy_mask_threshold is not None:
        off_policy_mask = get_off_policy_mask(
            advantages=advantages,
            per_token_logps=new,
            old_per_token_logps=old,
            mask=mask,
            off_policy_threshold=off_policy_mask_threshold,
        )

    with torch.no_grad():
        if use_vllm and sampling_per_token_logps is not None:
            # Filter out extra leading prompt tokens after left-padding input_ids.
            # Match TRL: aggregate log-ratios then exp (product), not sum of exp ratios.
            importance_sampling_ratio = (old - sampling_per_token_logps) * mask

            if vllm_importance_sampling_mode in ["sequence_mask", "sequence_truncate"]:
                importance_sampling_ratio = importance_sampling_ratio.sum(dim=-1, keepdim=True)

            importance_sampling_ratio = torch.exp(importance_sampling_ratio)

            if vllm_importance_sampling_mode in ["token_truncate", "sequence_truncate"]:
                importance_sampling_ratio = torch.clamp(
                    importance_sampling_ratio, 
                    min=vllm_importance_sampling_clip_min,
                    max=vllm_importance_sampling_clip_max
                )
            elif vllm_importance_sampling_mode in ["token_mask", "sequence_mask"]:
                min_val = (
                    vllm_importance_sampling_clip_min
                    if vllm_importance_sampling_clip_min is not None
                    else -math.inf
                )

                max_val = (
                    vllm_importance_sampling_clip_max
                    if vllm_importance_sampling_clip_max is not None
                    else math.inf
                )

                invalid_mis_mask = (importance_sampling_ratio < min_val) | (
                        importance_sampling_ratio > max_val
                )

                importance_sampling_ratio = importance_sampling_ratio.masked_fill(
                        invalid_mis_mask, value=0.0
                )
            else:
                raise ValueError(
                        f"Unknown vLLM importance sampling mode: {vllm_importance_sampling_mode}. Possible values are 'token_truncate', 'token_mask', 'sequence_truncate', and 'sequence_mask'."
                )
    pass

    # Must detach when old is None: exp(new - new.detach()) == 1 but keeps grads correct.
    if old is not None:
        log_ratio = new - old
    else:
        log_ratio = new - new.detach()

    if importance_sampling_level == "token":
        log_importance_weights = log_ratio
    elif importance_sampling_level == "sequence":
        log_importance_weights = (log_ratio * mask).sum(-1) / mask.sum(-1).clamp(min=1.0)
        log_importance_weights = log_importance_weights.unsqueeze(-1)
    else:
        raise ValueError(
            f"Unknown importance sampling level: {importance_sampling_level}. Possible values are 'token' "
            "and 'sequence'."
        )

    coef_1 =  torch.exp(log_importance_weights)

    # Reverse KL: low-variance low-bias estimator as used in the GRPO paper.
    if beta != 0.0:
        kl_i = torch.exp(ref - new) - (ref - new) - 1.0

    else:
        # Zeros with the correct shape.
        if importance_sampling_level == "sequence":
            kl_i = new.new_zeros(new.size(0), 1)
        else:
            kl_i = torch.zeros_like(new)

    if loss_type == "cispo":
        clamped_ratios = torch.clamp(coef_1, max=epsilon_high).detach()
        loss_i = -clamped_ratios * advantages * new
    elif loss_type in ["grpo", "bnpo", "dr_grpo", "dapo", "luspo"]:
        coef_2 = torch.clamp(coef_1, 1 - epsilon_low, 1 + epsilon_high)

        if delta is not None:
            loss_1 = torch.clamp(coef_1, max=delta) * advantages
        else:
            loss_1 = coef_1 * advantages
        pass
        loss_2 = coef_2 * advantages
        loss_i = -torch.min(loss_1, loss_2)
    elif loss_type == "sapo":
        temperatures = torch.where(advantages > 0, sapo_temperature_pos, sapo_temperature_neg)
        soft_coef_1 = torch.sigmoid(temperatures * (coef_1 - 1)) * 4 / temperatures
        loss_i = -soft_coef_1 * advantages
    elif loss_type == "vespo":
        if get_gamma_weights is None:
            raise Exception("vespo is only available in TRL 0.26.0+")
        phi_seq = get_gamma_weights(
            advantages=advantages,
            log_ratio_per_token=log_ratio,
            mask=mask,
            importance_sampling_ratio=importance_sampling_ratio,
            k_pos=vespo_k_pos,
            lambda_pos=vespo_lambda_pos,
            k_neg=vespo_k_neg,
            lambda_neg=vespo_lambda_neg,
        )
        loss_i = -phi_seq * advantages * new
    else:
        raise ValueError(f"Unknown loss type: {loss_type}")

    if off_policy_mask_threshold is not None:
        loss_i = loss_i * off_policy_mask

    if use_vllm and sampling_per_token_logps is not None:
        # vespo applies the IS ratio inside get_gamma_weights, so skip it here.
        if loss_type != "vespo":
            loss_i = loss_i * importance_sampling_ratio
        # delta for the metric.
        with torch.no_grad():
            delta = torch.abs(old - sampling_per_token_logps)
            delta = delta * mask
            flat_is_ratio = importance_sampling_ratio * mask
    else:
        delta = torch.tensor([]).detach()
        flat_is_ratio = torch.tensor([]).detach()
    if beta != 0.0:
        loss_i = loss_i + beta * kl_i

    mask = mask.to(torch.float32)
    n_mask_per_reward = mask.sum(1)

    # https://github.com/huggingface/trl/blob/e8b8499f1f8d76838155b515e414ee98f757d6d5/trl/trainer/grpo_trainer.py#L1624
    if loss_type in ["grpo", "sapo"]:
        loss = ((loss_i * mask).sum(-1) / mask.sum(-1).clamp(min=1.0)).mean()
        loss = loss / current_gradient_accumulation_steps
    elif loss_type == "bnpo":
        loss = (loss_i * mask).sum() / mask.sum().clamp(min=1.0)
        loss = loss / current_gradient_accumulation_steps
    elif loss_type == "dr_grpo":
        loss = (loss_i * mask).sum() / (loss_i.size(0) * max_completion_length)
        loss = loss / current_gradient_accumulation_steps
    elif loss_type in ["cispo", "dapo", "vespo"]:
        normalizer = num_items_in_batch/ num_processes
        loss = (loss_i * mask).sum() / normalizer
    elif loss_type == "luspo":
        loss = (loss_i * mask.sum(1, keepdim=True)).mean()
        normalizer = current_gradient_accumulation_steps
        loss = loss / normalizer
    else:
        raise ValueError(f"Unknown loss type: {loss_type}")

    # Folded metrics.
    def masked_batch_mean(x):
        with torch.inference_mode():
            completion_length = n_mask_per_reward.mean()
            if x.shape[1] == 1:  # when importance_sampling_level == "sequence"
                return completion_length, x.mean()
            else:
                mean_kl_per_reward = (x * mask).sum(1) / n_mask_per_reward
                mean_kl = mean_kl_per_reward.mean()
                return completion_length, mean_kl
    completion_length, mean_kl = masked_batch_mean(kl_i)
    return loss, completion_length, mean_kl, delta, flat_is_ratio, coef_1, mask

def grpo_update_SamplingParams(SamplingParams, generation_kwargs, vllm_sampling_params = None):
    good_sampling_params_keys = inspect.signature(SamplingParams).parameters.keys()

    new_generation_kwargs = {}
    for key in generation_kwargs.keys():
        if key in good_sampling_params_keys:
            new_generation_kwargs[key] = generation_kwargs[key]
    generation_kwargs = new_generation_kwargs

    if vllm_sampling_params is not None:
        for key in good_sampling_params_keys:
            if hasattr(vllm_sampling_params, key):
                overwrited_key = getattr(vllm_sampling_params, key)
                if overwrited_key is not None and (type(overwrited_key) in (list, tuple,) and len(overwrited_key) != 0):
                    generation_kwargs[key] = overwrited_key
    return generation_kwargs

def _get_inference_mode_context_manager(model: torch.nn.Module):
    """
    If the state dict was quantized using torchao, we will run into
    the following error when calling ops like aten.t() in inference mode.
    This is a bug in PyTorch that affects all tensor subclasses.

        Cannot set version_counter for inference tensor

    For now, we work around this issue by using `torch.no_grad()` in this case.
    See https://github.com/pytorch/pytorch/issues/164872 for more details.
    Otherwise, just return `torch.inference_mode()`.
    """
    torchao_config = getattr(model, "torchao_config", None)
    if torchao_config is not None and torchao_config.qat_scheme is None:
        return torch.no_grad()
    else:
        return torch.inference_mode()

import os as _unsloth_os
UNSLOTH_ENABLE_LOGGING = _unsloth_os.environ.get('UNSLOTH_ENABLE_LOGGING', '0') in ('1', 'True', 'true')

UNSLOTH_GRPO_SEQ_PACKING_ON = _unsloth_os.environ.get('UNSLOTH_GRPO_SEQ_PACKING', '1').lower() not in ('0', 'false', 'no', 'off')

try:
    import inspect as _unsloth_inspect
    from unsloth_zoo.rl_replacements import RL_REPLACEMENTS as _unsloth_zoo_RL
    UNSLOTH_ZOO_HAS_MASKED_COL_GUARD = 'torch.where(_keep, new' in _unsloth_inspect.getsource(_unsloth_zoo_RL['grpo_compute_loss'])
except Exception:
    UNSLOTH_ZOO_HAS_MASKED_COL_GUARD = False

_pg_build_layout = _pg_enabled_fn = _pg_verify_on = _pg_tol_ok = _PG_TOL_KILL = None
UNSLOTH_GRPO_PREFIX_GROUPER_ON = _unsloth_os.environ.get('UNSLOTH_GRPO_PREFIX_GROUPER', '1').lower() not in ('0', 'false', 'no', 'off')
if UNSLOTH_GRPO_PREFIX_GROUPER_ON:
    try:
        from unsloth.utils.prefix_grouper import build_group_layout as _pg_build_layout, prefix_grouper_enabled as _pg_enabled_fn, verify_on as _pg_verify_on, tol_ok as _pg_tol_ok, TOL_KILL as _PG_TOL_KILL
    except Exception:
        UNSLOTH_GRPO_PREFIX_GROUPER_ON = False

def vLLMSamplingParams(**kwargs):
    from vllm import SamplingParams

    sampling_params = SamplingParams(**kwargs)
    sampling_params._set_kwargs = kwargs
    return sampling_params
@dataclass
class UnslothGRPOConfig(GRPOConfig):
    """
    
    Configuration class for the [`GRPOTrainer`].

    This class includes only the parameters that are specific to GRPO training. For a full list of training arguments,
    please refer to the [`~transformers.TrainingArguments`] documentation. Note that default values in this class may
    differ from those in [`~transformers.TrainingArguments`].

    Using [`~transformers.HfArgumentParser`] we can turn this class into
    [argparse](https://docs.python.org/3/library/argparse#module-argparse) arguments that can be specified on the
    command line.

    Parameters:
        > Parameters that control the model and reference model

        model_init_kwargs (`str`, `dict[str, Any]`, *optional*):
            Keyword arguments for [`~transformers.AutoModelForCausalLM.from_pretrained`], used when the `model`
            argument of the [`GRPOTrainer`] is provided as a string.
        disable_dropout (`bool`, *optional*, defaults to `False`):
            Whether to disable dropout in the model. This is useful for training with a reference model, as it prevents
            the model from generating different logprobs for the same input.

        > Parameters that control the data preprocessing

        remove_unused_columns (`bool`, *optional*, defaults to `False`):
            Whether to only keep the column `"prompt"` in the dataset. If you use a custom reward function that
            requires any column other than `"prompts"` and `"completions"`, you should keep this to `False`.
        max_prompt_length (`int` or `None`, *optional*, defaults to `512`):
            Maximum length of the prompt. If the prompt is longer than this value, it will be truncated left.
        num_generations (`int` or `None`, *optional*, defaults to `8`):
            Number of generations per prompt to sample. The effective batch size (num_processes * per_device_batch_size
            * gradient_accumulation_steps) must be evenly divisible by this value.
        max_completion_length (`int` or `None`, *optional*, defaults to `256`):
            Maximum length of the generated completion.
        ds3_gather_for_generation (`bool`, *optional*, defaults to `True`):
            This setting applies to DeepSpeed ZeRO-3. If enabled, the policy model weights are gathered for generation,
            improving generation speed. However, disabling this option allows training models that exceed the VRAM
            capacity of a single GPU, albeit at the cost of slower generation. Disabling this option is not compatible
            with vLLM generation.
        shuffle_dataset (`bool`, *optional*, defaults to `True`):
            Whether to shuffle the training dataset.

        > Parameters that control generation

        generation_batch_size: (`int`, *optional*):
            Batch size to use for generation. If `None`, it defaults to the effective training batch size:
            `per_device_train_batch_size * num_processes * steps_per_generation`. In other words, there is one
            generation batch processed per optimization step. Mutually exclusive with `steps_per_generation`.
        steps_per_generation: (`int`, *optional*):
            Number of steps per generation. If `None`, it defaults to `gradient_accumulation_steps`. Mutually exclusive
            with `generation_batch_size`.
        temperature (`float`, defaults to `1.0`):
            Temperature for sampling. The higher the temperature, the more random the completions.
        top_p (`float`, *optional*, defaults to `1.0`):
            Float that controls the cumulative probability of the top tokens to consider. Must be in (0, 1]. Set to
            `1.0` to consider all tokens.
        top_k (`int`, *optional*):
            Number of highest probability vocabulary tokens to keep for top-k-filtering. If `None`, top-k-filtering is
            disabled and all tokens are considered.
        min_p (`float`, *optional*):
            Minimum token probability, which will be scaled by the probability of the most likely token. It must be a
            value between `0.0` and `1.0`. Typical values are in the `0.01-0.2` range.
        repetition_penalty (`float`, *optional*, defaults to `1.0`):
            Float that penalizes new tokens based on whether they appear in the prompt and the generated text so far.
            Values > `1.0` encourage the model to use new tokens, while values < `1.0` encourage the model to repeat
            tokens.
        use_transformers_paged (`bool`, *optional*, defaults to `False`):
            Whether to use the `transformers` paged implementation for generation. If set to `True`, the `transformers`
            paged implementation will be used for generation instead of the default padded implementation. This
            parameter is only effective when `use_vllm` is set to `False`.
        cache_implementation (`str`, *optional*):
            Implementation of the cache method for faster generation when `use_vllm` is set to `False`.
        generation_kwargs (`dict[str, Any]`, *optional*):
            Additional keyword arguments to pass to [`~transformers.GenerationConfig`] (if using transformers) or
            `SamplingParams` (if using vLLM) when sampling completions. This can be used to further customize the
            generation behavior, such as setting `suppress_tokens`, `num_beams`, etc. If it contains keys that conflict
            with the other generation parameters (like `min_p`, `top_p`, etc.), they will override them.

        > Parameters that control generation acceleration powered by vLLM

        use_vllm (`bool`, *optional*, defaults to `False`):
            Whether to use vLLM for generating completions. If set to `True`, the trainer will use vLLM for generation
            instead of the default model.generate(). Requires `vllm` to be installed.
        vllm_mode (`str`, *optional*, defaults to `"server"`):
            Mode to use for vLLM integration when `use_vllm` is set to `True`. Must be one of `"server"` or
            `"colocate"`.

            - `"server"`: The trainer will send generation requests to a separate vLLM server. Make sure a TRL vLLM
              server is running (start with `trl vllm-serve`).
            - `"colocate"`: vLLM will run in the same process and share the training GPUs. This avoids the need for a
              separate server but may cause resource contention with training.
        vllm_model_impl (`str`, *optional*, defaults to `"vllm"`):
            Model implementation to use for vLLM. Must be one of `"transformers"` or `"vllm"`. `"transformers"`: Use
            the `transformers` backend for model implementation. `"vllm"`: Use the `vllm` library for model
            implementation.
        vllm_guided_decoding_regex (`str`, *optional*):
            Regex for vLLM guided decoding. If `None` (default), guided decoding is disabled.

        > Parameters that control the vLLM server (only used when `vllm_mode` is `"server"`)

        vllm_server_base_url (`str`, *optional*):
            Base URL for the vLLM server (e.g., `"http://localhost:8000"`). If provided, `vllm_server_host` and
            `vllm_server_port` are ignored.
        vllm_server_host (`str`, *optional*, defaults to `"0.0.0.0"`):
            Host of the vLLM server to connect to. Ignored if `vllm_server_base_url` is provided.
        vllm_server_port (`int`, *optional*, defaults to `8000`):
            Port of the vLLM server to connect to. Ignored if `vllm_server_base_url` is provided.
        vllm_server_timeout (`float`, *optional*, defaults to `240.0`):
            Total timeout duration in seconds to wait for the vLLM server to be up. If the server is not up after the
            timeout, a `ConnectionError` is raised.

        > Parameters that control colocated vLLM execution (only used when `vllm_mode` is `"colocate"`)

        vllm_gpu_memory_utilization (`float`, *optional*, defaults to `0.3`):
            Control the GPU memory utilization for vLLM. This setting only applies when `vllm_mode` is set to
            `"colocate"`. If you are using `vllm_mode="server"`, this parameter must be passed separately when
            launching the vLLM server via the `--vllm_gpu_memory_utilization` flag.
        vllm_tensor_parallel_size (`int`, *optional*, defaults to `1`):
            Control the tensor parallel size for vLLM. This setting only applies when `vllm_mode` is set to
            `"colocate"`. If you are using `vllm_mode="server"`, this parameter must be passed separately when
            launching the vLLM server via the `--vllm_tensor_parallel_size` flag.
        vllm_enable_sleep_mode (`bool`, *optional*, defaults to `False`):
            Whether to enable sleep mode for vLLM. If `True`, vLLM will sleep during the optimization step and woken
            for weight sync and generation.

        > Parameters that control the training

        beta (`float`, *optional*, defaults to `0.0`):
            KL coefficient. If `0.0` (default), the reference model is not loaded, reducing memory usage and improving
            training speed.
        num_iterations (`int`, *optional*, defaults to `1`):
            Number of iterations per batch (denoted as μ in the algorithm).
        epsilon (`float`, *optional*, defaults to `0.2`):
            Epsilon value for clipping.
        delta (`float`, *optional*):
            Enables the upper clipping bound in two-sided GRPO loss when set to a float. If `None` (default), standard
            GRPO clipping is used. Recommended to be greater than `1 + ε` when enabled. This method is introduced in
            the [INTELLECT-2 tech report](https://huggingface.co/papers/2505.07291).
        epsilon_high (`float`, *optional*):
            Upper-bound epsilon value for clipping. If not specified, it defaults to the same value as the lower-bound
            specified in argument `epsilon`. Paper [DAPO](https://huggingface.co/papers/2503.14476) recommends `0.28`.
        importance_sampling_level (`str`, *optional*, defaults to `"token"`):
            Controls whether importance sampling ratios are computed at the `"token"` or `"sequence"` level. `"token"`
            keeps the raw per-token log-probability ratios (one weight per token). `"sequence"` averages the
            log-probability ratios across valid tokens to produce a single ratio per sequence. The [GSPO
            paper](https://huggingface.co/papers/2507.18071) shows that sequence-level sampling often yields more
            stable training and better alignment with sequence-level rewards.
        reward_weights (`list[float]`, *optional*):
            Weights for each reward function. Must match the number of reward functions. If `None`, all rewards are
            weighted equally with weight `1.0`.
        scale_rewards (`str` or `bool`, *optional*, defaults to `"group"`):
            Specifies the scaling strategy for rewards. Supported values are:

            - `True` or `"group"` (default): rewards are scaled by the standard deviation within each group, ensuring
              unit variance within a group.
            - `"batch"`: rewards are scaled by the standard deviation across the entire batch, as recommended in the
              [PPO Lite paper](https://huggingface.co/papers/2508.08221).
            - `False` or `"none"`: no scaling is applied. The [Dr. GRPO
              paper](https://huggingface.co/papers/2503.20783) recommends not scaling rewards, as scaling by the
              standard deviation introduces a question-level difficulty bias.
        loss_type (`str`, *optional*, defaults to `"dapo"`):
            Specifies the loss formulation to use. Supported values are:

            - `"grpo"`: Aggregates token-level losses by normalizing over sequence length. Not recommended due to
              length bias—this approach tends to prefer shorter completions with positive advantages and longer ones
              with negative advantages.
            - `"dr_grpo"`: Aggregates token-level losses by normalizing with a global constant. This method was
              introduced in the [Dr. GRPO paper](https://huggingface.co/papers/2503.20783) to eliminate length bias.
              The value of the constant corresponds to `max_completion_length`.
            - `"dapo"` (default): Aggregates token-level losses by normalizing with the number of active token in the
              global accumulated batch. This method was introduced in the [DAPO
              paper](https://huggingface.co/papers/2503.14476) to eliminate length bias.
            - `"bnpo"`: Aggregates token-level losses by normalizing with the number of active token in the local
              batch. Note that normalization is performed over the local batch only, so results may slightly vary
              depending on the local batch size, despite a constant effective batch size. When using
              `per_device_train_batch_size==1`, the loss is equivalent to the GRPO loss.
        mask_truncated_completions (`bool`, *optional*, defaults to `False`):
            When enabled, truncated completions are excluded from the loss calculation, preventing them from being
            incorrectly penalized and introducing noise during training. According to the
            [DAPO](https://huggingface.co/papers/2503.14476) paper, this is a good practice for training stability.
        sync_ref_model (`bool`, *optional*, defaults to `False`):
            Whether to synchronize the reference model with the active model every `ref_model_sync_steps` steps, using
            the `ref_model_mixup_alpha` parameter. This synchronization originates from the
            [TR-DPO](https://huggingface.co/papers/2404.09656) paper.
        ref_model_mixup_alpha (`float`, *optional*, defaults to `0.6`):
            α parameter from the [TR-DPO](https://huggingface.co/papers/2404.09656) paper, which controls the mix
            between the current policy and the previous reference policy during updates. The reference policy is
            updated according to the equation: `π_ref = α * π_θ + (1 - α) * π_ref_prev`. To use this parameter, you
            must set `sync_ref_model=True`.
        ref_model_sync_steps (`int`, *optional*, defaults to `512`):
            τ parameter from the [TR-DPO](https://huggingface.co/papers/2404.09656) paper, which determines how
            frequently the current policy is synchronized with the reference policy. To use this parameter, you must
            set `sync_ref_model=True`.
        top_entropy_quantile (`float`, *optional*, defaults to `1.0`):
            ρ parameter from [Beyond the 80/20 Rule](https://huggingface.co/papers/2506.01939). Keeps in the policy
            loss term only the top-ρ quantile of tokens by entropy of the probability distribution at each sequence
            position, improving results. Range: `[0.0-1.0]`. A value of `0.0` masks all but the highest entropy token;
            `1.0` keeps all tokens. The paper recommends a value of `0.2`. If used with
            `mask_truncated_completions=True`, only tokens from non-truncated completions are considered.
        use_liger_loss (`bool`, *optional*, defaults to `False`):
            Whether to use the Liger GRPO loss.
        vllm_importance_sampling_correction (`bool`, *optional*, defaults to `True`):
            Whether to apply Truncated Importance Sampling (TIS) between vLLM completion logprobs and recomputed
            logprobs. [Your Efficient RL Framework Secretly Brings You Off-Policy RL
            Training](https://fengyao.notion.site/off-policy-rl) highlights that using a separate generation framework
            (such as vLLM) can introduce off-policy effects due to subtle implementation differences between generation
            and training backends. TIS is proposed as a remedy for this issue.
        vllm_importance_sampling_cap (`float`, *optional*, defaults to `2.0`):
            Truncation parameter C for Truncated Importance Sampling (TIS). This sets an upper bound on the importance
            sampling ratio, improving training stability.

        > Parameters that control the logging

        log_completions (`bool`, *optional*, defaults to `False`):
            Whether to log a sample of (prompt, completion) pairs every `logging_steps` steps. If `rich` is installed,
            it prints the sample. If `wandb` logging is enabled, it logs it to `wandb`.
        num_completions_to_print (`int`, *optional*):
            Number of completions to print with `rich`. If `None`, all completions are logged.
        wandb_log_unique_prompts (`bool`, *optional*, defaults to `False`):
            Whether to log unique prompts in wandb. If `True`, only unique prompts are logged. If `False`, all prompts
            are logged.
    
    """
    vllm_sampling_params: Optional[Any] = field(
        default = None,
        metadata = {'help': 'vLLM SamplingParams'},
    )
    unsloth_num_chunks : Optional[int] = field(
        default = -1,
        metadata = {'help': 'Chunk size to reduce memory usage. -1 is most efficient.'},
    )
    unsloth_logit_chunk_multiplier : Optional[int] = field(
            default = None,
            metadata = {'help': 'Multiplier for chunked logit computations.'},
        )
    unsloth_grpo_mini_batch : Optional[int] = field(
        default = None,
        metadata = {'help': 'Mini batch size for GRPO hidden state accumulation. Default is None unless user defines it.'},
    )
    
    def __init__(
        self,
        output_dir = None,
        per_device_train_batch_size = 4,
        num_train_epochs = 3.0,
        max_steps = -1,
        learning_rate = 5e-05,
        lr_scheduler_type = 'linear',
        lr_scheduler_kwargs = None,
        warmup_steps = 0.1,
        optim = 'adamw_8bit',
        optim_args = None,
        weight_decay = 0.001,
        adam_beta1 = 0.9,
        adam_beta2 = 0.999,
        adam_epsilon = 1e-08,
        optim_target_modules = None,
        gradient_accumulation_steps = 2,
        average_tokens_across_devices = True,
        max_grad_norm = 1.0,
        label_smoothing_factor = 0.0,
        bf16 = False,
        fp16 = False,
        bf16_full_eval = False,
        fp16_full_eval = False,
        tf32 = None,
        gradient_checkpointing = True,
        gradient_checkpointing_kwargs = None,
        torch_compile = False,
        torch_compile_backend = None,
        torch_compile_mode = None,
        use_liger_kernel = False,
        liger_kernel_config = None,
        use_cache = False,
        neftune_noise_alpha = None,
        torch_empty_cache_steps = 250,
        auto_find_batch_size = False,
        logging_strategy = 'steps',
        logging_steps = 1,
        logging_first_step = False,
        log_on_each_node = True,
        logging_nan_inf_filter = False,
        include_num_input_tokens_seen = False,
        log_level = 'passive',
        log_level_replica = 'warning',
        disable_tqdm = None,
        report_to = 'none',
        run_name = None,
        project = 'huggingface',
        trackio_space_id = 'trackio',
        eval_strategy = 'no',
        eval_steps = None,
        eval_delay = 0,
        per_device_eval_batch_size = 4,
        prediction_loss_only = False,
        eval_on_start = False,
        eval_do_concat_batches = True,
        eval_use_gather_object = False,
        eval_accumulation_steps = 2,
        batch_eval_metrics = False,
        save_only_model = False,
        save_strategy = 'steps',
        save_steps = 500,
        save_on_each_node = False,
        save_total_limit = None,
        enable_jit_checkpoint = False,
        push_to_hub = False,
        hub_token = None,
        hub_private_repo = None,
        hub_model_id = None,
        hub_strategy = 'every_save',
        hub_always_push = False,
        hub_revision = None,
        load_best_model_at_end = False,
        metric_for_best_model = None,
        greater_is_better = None,
        ignore_data_skip = False,
        restore_callback_states_from_checkpoint = False,
        full_determinism = False,
        seed = 3407,
        data_seed = 3407,
        use_cpu = False,
        accelerator_config = None,
        parallelism_config = None,
        dataloader_drop_last = False,
        dataloader_num_workers = 0,
        dataloader_pin_memory = True,
        dataloader_persistent_workers = False,
        dataloader_prefetch_factor = None,
        remove_unused_columns = False,
        label_names = None,
        train_sampling_strategy = 'random',
        length_column_name = 'length',
        ddp_find_unused_parameters = None,
        ddp_bucket_cap_mb = None,
        ddp_broadcast_buffers = None,
        ddp_backend = None,
        ddp_timeout = 1800,
        fsdp = None,
        fsdp_config = None,
        deepspeed = None,
        debug = '',
        skip_memory_metrics = True,
        do_train = False,
        do_eval = False,
        do_predict = False,
        resume_from_checkpoint = None,
        warmup_ratio = None,
        logging_dir = None,
        local_rank = -1,
        model_init_kwargs = None,
        disable_dropout = False,
        max_prompt_length = 512,
        num_generations = 8,
        max_completion_length = 256,
        ds3_gather_for_generation = True,
        shuffle_dataset = True,
        generation_batch_size = None,
        steps_per_generation = None,
        temperature = 1.0,
        top_p = 1.0,
        top_k = None,
        min_p = None,
        generation_kwargs = {},
        repetition_penalty = 1.0,
        use_transformers_paged = False,
        cache_implementation = None,
        use_vllm = False,
        vllm_mode = 'colocate',
        vllm_model_impl = 'vllm',
        vllm_enable_sleep_mode = False,
        vllm_guided_decoding_regex = None,
        vllm_server_base_url = None,
        vllm_server_host = '0.0.0.0',
        vllm_server_port = 8000,
        vllm_server_timeout = 240.0,
        vllm_gpu_memory_utilization = 0.3,
        vllm_tensor_parallel_size = 1,
        beta = 0.001,
        num_iterations = 1,
        epsilon = 0.2,
        delta = None,
        epsilon_high = None,
        importance_sampling_level = 'token',
        reward_weights = None,
        scale_rewards = 'group',
        loss_type = 'bnpo',
        mask_truncated_completions = False,
        sync_ref_model = False,
        ref_model_mixup_alpha = 0.6,
        ref_model_sync_steps = 512,
        top_entropy_quantile = 1.0,
        use_liger_loss = False,
        vllm_importance_sampling_correction = False,
        vllm_importance_sampling_cap = 2.0,
        log_completions = False,
        num_completions_to_print = None,
        wandb_log_unique_prompts = False,
        vllm_sampling_params = None,
        unsloth_num_chunks = -1,
        unsloth_logit_chunk_multiplier = None,
        unsloth_grpo_mini_batch = None,
        
        **kwargs,
    ):
        if learning_rate < 1e-7: print(f'Unsloth: Your learning rate of `{learning_rate}` is too small and less than 1e-7! Consider increasing it, otherwise gradient updates will be close to 0!')
        if learning_rate > 1: print(f'Unsloth: Your learning rate of `{learning_rate}` is way too larger > 1! Consider decreasing it to 1e-1, otherwise gradient updates will explode!')
        if num_train_epochs is None:
            num_train_epochs = 3.0  # Default to 3 epochs if None, max_steps will override
        if output_dir is None and save_strategy == 'steps' and save_steps == 500:
            output_dir = 'unsloth_training_checkpoints'
            save_strategy = 'no'
        if loss_type.lower() == 'dr_grpo':
            loss_type = 'dr_grpo'
        elif loss_type.lower() == 'dapo':
            loss_type = 'dapo'
        if loss_type.lower() == 'dr_grpo':
            if scale_rewards == None:
                scale_rewards = True
            elif scale_rewards == True:
                print('Unsloth: The Dr GRPO paper recommends setting `scale_rewards` to False! Will override. Set it to `None` to force False.')
                scale_rewards = False
        elif loss_type.lower() == 'dapo':
            if mask_truncated_completions != True:
                print('Unsloth: The DAPO paper recommends `mask_truncated_completions = True` - we will set it.')
            if epsilon_high != 0.28:
                print('Unsloth: The DAPO paper recommends `epsilon_high = 0.28` - we will set it.')
            if beta != 0.0:
                print(f'[WARNING] Unsloth: The DAPO paper recommends setting `beta = 0.0` to remove the KL term - You have set it to {beta}.')
            mask_truncated_completions = True
            epsilon_high = 0.28
        
        if steps_per_generation is None and generation_batch_size is None:
            ga = gradient_accumulation_steps
            world_size = int(os.environ.get('WORLD_SIZE', '1'))
            if (ga * world_size * per_device_train_batch_size) % num_generations != 0:
                print('Unsloth: We now expect `per_device_train_batch_size` * `gradient_accumulation_steps` * `world_size` to be a multiple of `num_generations`.\nWe will change the batch size of ' + str(per_device_train_batch_size) + ' to the `num_generations` of ' + str(num_generations))
                per_device_train_batch_size = num_generations
        
        if temperature <= 0:
            raise ValueError('Unsloth: Please set a positive non-zero temperature since your results will be wrong.')
        elif temperature >= 10:
            raise ValueError('Unsloth: Please set a positive non-zero temperature less than 10, since sampling will be quite erratic.')
        
        if use_vllm and (top_k is None or top_k == 0): top_k = -1
        
        # One dict so the filter sees the mirrored parameters AND `**kwargs`:
        # filtering kwargs alone would double-bind any argument TRL renamed,
        # since the new name is itself a mirrored parameter.
        _unsloth_config_arguments = dict(
            output_dir = output_dir,
            per_device_train_batch_size = per_device_train_batch_size,
            num_train_epochs = num_train_epochs,
            max_steps = max_steps,
            learning_rate = learning_rate,
            lr_scheduler_type = lr_scheduler_type,
            lr_scheduler_kwargs = lr_scheduler_kwargs,
            warmup_steps = warmup_steps,
            optim = optim,
            optim_args = optim_args,
            weight_decay = weight_decay,
            adam_beta1 = adam_beta1,
            adam_beta2 = adam_beta2,
            adam_epsilon = adam_epsilon,
            optim_target_modules = optim_target_modules,
            gradient_accumulation_steps = gradient_accumulation_steps,
            average_tokens_across_devices = average_tokens_across_devices,
            max_grad_norm = max_grad_norm,
            label_smoothing_factor = label_smoothing_factor,
            bf16 = bf16,
            fp16 = fp16,
            bf16_full_eval = bf16_full_eval,
            fp16_full_eval = fp16_full_eval,
            tf32 = tf32,
            gradient_checkpointing = gradient_checkpointing,
            gradient_checkpointing_kwargs = gradient_checkpointing_kwargs,
            torch_compile = torch_compile,
            torch_compile_backend = torch_compile_backend,
            torch_compile_mode = torch_compile_mode,
            use_liger_kernel = use_liger_kernel,
            liger_kernel_config = liger_kernel_config,
            use_cache = use_cache,
            neftune_noise_alpha = neftune_noise_alpha,
            torch_empty_cache_steps = torch_empty_cache_steps,
            auto_find_batch_size = auto_find_batch_size,
            logging_strategy = logging_strategy,
            logging_steps = logging_steps,
            logging_first_step = logging_first_step,
            log_on_each_node = log_on_each_node,
            logging_nan_inf_filter = logging_nan_inf_filter,
            include_num_input_tokens_seen = include_num_input_tokens_seen,
            log_level = log_level,
            log_level_replica = log_level_replica,
            disable_tqdm = disable_tqdm,
            report_to = report_to,
            run_name = run_name,
            project = project,
            trackio_space_id = trackio_space_id,
            eval_strategy = eval_strategy,
            eval_steps = eval_steps,
            eval_delay = eval_delay,
            per_device_eval_batch_size = per_device_eval_batch_size,
            prediction_loss_only = prediction_loss_only,
            eval_on_start = eval_on_start,
            eval_do_concat_batches = eval_do_concat_batches,
            eval_use_gather_object = eval_use_gather_object,
            eval_accumulation_steps = eval_accumulation_steps,
            batch_eval_metrics = batch_eval_metrics,
            save_only_model = save_only_model,
            save_strategy = save_strategy,
            save_steps = save_steps,
            save_on_each_node = save_on_each_node,
            save_total_limit = save_total_limit,
            enable_jit_checkpoint = enable_jit_checkpoint,
            push_to_hub = push_to_hub,
            hub_token = hub_token,
            hub_private_repo = hub_private_repo,
            hub_model_id = hub_model_id,
            hub_strategy = hub_strategy,
            hub_always_push = hub_always_push,
            hub_revision = hub_revision,
            load_best_model_at_end = load_best_model_at_end,
            metric_for_best_model = metric_for_best_model,
            greater_is_better = greater_is_better,
            ignore_data_skip = ignore_data_skip,
            restore_callback_states_from_checkpoint = restore_callback_states_from_checkpoint,
            full_determinism = full_determinism,
            seed = seed,
            data_seed = data_seed,
            use_cpu = use_cpu,
            accelerator_config = accelerator_config,
            parallelism_config = parallelism_config,
            dataloader_drop_last = dataloader_drop_last,
            dataloader_num_workers = dataloader_num_workers,
            dataloader_pin_memory = dataloader_pin_memory,
            dataloader_persistent_workers = dataloader_persistent_workers,
            dataloader_prefetch_factor = dataloader_prefetch_factor,
            remove_unused_columns = remove_unused_columns,
            label_names = label_names,
            train_sampling_strategy = train_sampling_strategy,
            length_column_name = length_column_name,
            ddp_find_unused_parameters = ddp_find_unused_parameters,
            ddp_bucket_cap_mb = ddp_bucket_cap_mb,
            ddp_broadcast_buffers = ddp_broadcast_buffers,
            ddp_backend = ddp_backend,
            ddp_timeout = ddp_timeout,
            fsdp = fsdp,
            fsdp_config = fsdp_config,
            deepspeed = deepspeed,
            debug = debug,
            skip_memory_metrics = skip_memory_metrics,
            do_train = do_train,
            do_eval = do_eval,
            do_predict = do_predict,
            resume_from_checkpoint = resume_from_checkpoint,
            warmup_ratio = warmup_ratio,
            logging_dir = logging_dir,
            local_rank = local_rank,
            model_init_kwargs = model_init_kwargs,
            disable_dropout = disable_dropout,
            max_prompt_length = max_prompt_length,
            num_generations = num_generations,
            max_completion_length = max_completion_length,
            ds3_gather_for_generation = ds3_gather_for_generation,
            shuffle_dataset = shuffle_dataset,
            generation_batch_size = generation_batch_size,
            steps_per_generation = steps_per_generation,
            temperature = temperature,
            top_p = top_p,
            top_k = top_k,
            min_p = min_p,
            generation_kwargs = generation_kwargs,
            repetition_penalty = repetition_penalty,
            use_transformers_paged = use_transformers_paged,
            cache_implementation = cache_implementation,
            use_vllm = use_vllm,
            vllm_mode = vllm_mode,
            vllm_model_impl = vllm_model_impl,
            vllm_enable_sleep_mode = vllm_enable_sleep_mode,
            vllm_guided_decoding_regex = vllm_guided_decoding_regex,
            vllm_server_base_url = vllm_server_base_url,
            vllm_server_host = vllm_server_host,
            vllm_server_port = vllm_server_port,
            vllm_server_timeout = vllm_server_timeout,
            vllm_gpu_memory_utilization = vllm_gpu_memory_utilization,
            vllm_tensor_parallel_size = vllm_tensor_parallel_size,
            beta = beta,
            num_iterations = num_iterations,
            epsilon = epsilon,
            delta = delta,
            epsilon_high = epsilon_high,
            importance_sampling_level = importance_sampling_level,
            reward_weights = reward_weights,
            scale_rewards = scale_rewards,
            loss_type = loss_type,
            mask_truncated_completions = mask_truncated_completions,
            sync_ref_model = sync_ref_model,
            ref_model_mixup_alpha = ref_model_mixup_alpha,
            ref_model_sync_steps = ref_model_sync_steps,
            top_entropy_quantile = top_entropy_quantile,
            use_liger_loss = use_liger_loss,
            vllm_importance_sampling_correction = vllm_importance_sampling_correction,
            vllm_importance_sampling_cap = vllm_importance_sampling_cap,
            log_completions = log_completions,
            num_completions_to_print = num_completions_to_print,
            wandb_log_unique_prompts = wandb_log_unique_prompts,**kwargs)
        super().__init__(**_unsloth_filter_config_init_kwargs(GRPOConfig, _unsloth_config_arguments))
        self.vllm_sampling_params = vllm_sampling_params
        self.unsloth_num_chunks = unsloth_num_chunks
        if unsloth_grpo_mini_batch is not None:
            if self.generation_batch_size >= unsloth_grpo_mini_batch:
                self.unsloth_grpo_mini_batch = unsloth_grpo_mini_batch
            else:
                raise ValueError(
                    f"Unsloth GRPO mini batch size needs to be less than or equal to the effective generation batch size, "
                    f"which is self.per_device_train_batch_size * gradient_accumulation_steps."
                )
        self.unsloth_logit_chunk_multiplier = unsloth_logit_chunk_multiplier
        

pass

class _UnslothGRPOTrainer(BaseTrainer):
    """"""

    _tag_names = ["trl", "grpo"]
    _name = "GRPO"
    _paper = {
        "title": "DeepSeekMath: Pushing the Limits of Mathematical Reasoning in Open Language Models",
        "id": "2402.03300",
        # docstyle-ignore
        "citation": textwrap.dedent("""\
            @article{shao2024deepseekmath,
                title        = {{DeepSeekMath: Pushing the Limits of Mathematical Reasoning in Open Language Models}},
                author       = {Zhihong Shao and Peiyi Wang and Qihao Zhu and Runxin Xu and Junxiao Song and Mingchuan Zhang and Y. K. Li and Y. Wu and Daya Guo},
                year         = 2024,
                eprint       = {arXiv:2402.03300},
            }
            """),
    }

    def __init__(
        self,
        model: Union[str, PreTrainedModel],
        reward_funcs: Union[RewardFunc, list[RewardFunc]],
        args: Optional[GRPOConfig] = None,
        train_dataset: Optional[Union[Dataset, IterableDataset]] = None,
        eval_dataset: Optional[Union[Dataset, IterableDataset, dict[str, Union[Dataset, IterableDataset]]]] = None,
        processing_class: Optional[Union[PreTrainedTokenizerBase, ProcessorMixin]] = None,
        reward_processing_classes: Optional[Union[PreTrainedTokenizerBase, list[PreTrainedTokenizerBase]]] = None,
        callbacks: Optional[list[TrainerCallback]] = None,
        optimizers: tuple[Optional[torch.optim.Optimizer], Optional[torch.optim.lr_scheduler.LambdaLR]] = (None, None),
        peft_config: Optional["PeftConfig"] = None,
    ):

        if hasattr(model, 'vllm_engine') and hasattr(args, 'use_vllm'):
            if (getattr(args, 'use_vllm', False) == False):
                args.use_vllm = True
            args.vllm_mode='colocate'
            _unsloth_esm = getattr(getattr(getattr(getattr(model.vllm_engine, 'llm_engine', None), 'vllm_config', None), 'model_config', None), 'enable_sleep_mode', None)
            if (_unsloth_esm if _unsloth_esm is not None else os.environ.get('UNSLOTH_VLLM_STANDBY', '0') != '0'):
                args.vllm_enable_sleep_mode=True
        # Args
        if args is None:
            model_name = model if isinstance(model, str) else model.config._name_or_path
            model_name = model_name.split("/")[-1]
            args = GRPOConfig(f"{model_name}-GRPO")

        # Models
        # Trained model
        model_init_kwargs = args.model_init_kwargs or {}
        if isinstance(model, str):
            model_id = model
            dtype = model_init_kwargs.get("dtype")
            if isinstance(dtype, torch.dtype) or dtype == "auto" or dtype is None:
                pass  # dtype is already a torch.dtype or "auto" or None
            elif isinstance(dtype, str):  # it's a str, but not "auto"
                dtype = getattr(torch, dtype)
                model_init_kwargs["dtype"] = dtype
            else:
                raise ValueError(
                    "Invalid `dtype` passed to `GRPOConfig`. Expected either 'auto' or a string representing "
                    f"a `torch.dtype` (e.g., 'float32'), but got {dtype}."
                )
            # Disable caching if gradient checkpointing is enabled [not supported]
            config = AutoConfig.from_pretrained(model_id)
            architecture = getattr(transformers, config.architectures[0])
            model = architecture.from_pretrained(model_id, **model_init_kwargs)
        else:
            model_id = model.config._name_or_path
            if args.model_init_kwargs is not None:
                logger.warning(
                    "You passed `model_init_kwargs` to the `GRPOConfig`, but your model is already instantiated. "
                    "The `model_init_kwargs` will be ignored."
                )

        # Some models [SmolVLM/Idefics3] don't support `logits_to_keep` argument and error out if we pass it
        # Inspect the forward method before we wrap the model with PEFT
        self.model_kwarg_keys = (
            inspect.signature(model.forward).parameters.keys()
            if not hasattr(model, "get_base_model")
            else inspect.signature(model.get_base_model().forward).parameters.keys()
        )

        if False:
            pass

        # Processing class
        if processing_class is None:
            processing_class = AutoProcessor.from_pretrained(model.config._name_or_path, truncation_side="left")

        # Handle pad token for processors or tokenizers
        if isinstance(processing_class, ProcessorMixin):
            tokenizer = processing_class.tokenizer
        elif isinstance(processing_class, PreTrainedTokenizerBase):
            tokenizer = processing_class
        else:
            raise TypeError("The `processing_class` must be either a `PreTrainedTokenizerBase` or a `ProcessorMixin`")

        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        self.pad_token = tokenizer.pad_token
        self.pad_token_id = tokenizer.pad_token_id
        self.eos_token_id = tokenizer.eos_token_id

        # Reward functions
        if not isinstance(reward_funcs, list):
            reward_funcs = [reward_funcs]
        self.reward_func_names = []
        for i, reward_func in enumerate(reward_funcs):
            if isinstance(reward_func, str):
                reward_funcs[i] = AutoModelForSequenceClassification.from_pretrained(
                    reward_func, num_labels=1, **model_init_kwargs
                )
            if isinstance(reward_funcs[i], nn.Module):  # Use Module over PretrainedModel for compat w/ compiled models
                self.reward_func_names.append(reward_funcs[i].config._name_or_path.split("/")[-1])
            else:
                self.reward_func_names.append(reward_funcs[i].__name__)
        self.reward_funcs = reward_funcs

        # Reward weights
        if args.reward_weights is not None:
            if len(args.reward_weights) != len(reward_funcs):
                raise ValueError(
                    f"Number of reward weights ({len(args.reward_weights)}) must match number of reward "
                    f"functions ({len(reward_funcs)})"
                )
            self.reward_weights = torch.tensor(args.reward_weights, dtype=torch.float32)
        else:
            self.reward_weights = torch.ones(len(reward_funcs), dtype=torch.float32)

        # Reward processing class
        if reward_processing_classes is None:
            reward_processing_classes = [None] * len(reward_funcs)
        elif not isinstance(reward_processing_classes, list):
            reward_processing_classes = [reward_processing_classes]
        if len(reward_processing_classes) != len(reward_funcs):
            raise ValueError(
                f"The number of reward processing classes ({len(reward_processing_classes)}) must match the number of "
                f"reward functions ({len(reward_funcs)})."
            )

        for i, (reward_processing_class, reward_func) in enumerate(zip(reward_processing_classes, reward_funcs)):
            if isinstance(reward_func, PreTrainedModel):
                if reward_processing_class is None:
                    reward_processing_class = AutoTokenizer.from_pretrained(reward_func.config._name_or_path)
                if reward_processing_class.pad_token_id is None:
                    reward_processing_class.pad_token = reward_processing_class.eos_token
                # The reward model computes the reward for the latest non-padded token in the input sequence.
                # So it's important to set the pad token ID to the padding token ID of the processing class.
                reward_func.config.pad_token_id = reward_processing_class.pad_token_id
                reward_processing_classes[i] = reward_processing_class

        self.reward_processing_classes = reward_processing_classes

        # Training arguments
        self.max_prompt_length = args.max_prompt_length
        self.max_completion_length = args.max_completion_length  # = |o_i| in the GRPO paper
        self.num_generations = args.num_generations  # = G in the GRPO paper
        self.temperature = args.temperature
        self.top_p = args.top_p
        self.top_k = args.top_k
        self.min_p = args.min_p
        self.repetition_penalty = args.repetition_penalty
        self.use_transformers_paged = args.use_transformers_paged
        self.use_vllm = args.use_vllm
        self.vllm_mode = args.vllm_mode
        self.vllm_gpu_memory_utilization = args.vllm_gpu_memory_utilization  # only applies to colocation mode
        self.vllm_tensor_parallel_size = args.vllm_tensor_parallel_size  # only applies to colocation mode
        self.vllm_importance_sampling_correction = args.vllm_importance_sampling_correction
        self.vllm_importance_sampling_cap = args.vllm_importance_sampling_cap
        self.use_liger_loss = args.use_liger_loss
        self.loss_type = args.loss_type
        self.scale_rewards = args.scale_rewards
        self.importance_sampling_level = args.importance_sampling_level
        self.mask_truncated_completions = args.mask_truncated_completions
        self.top_entropy_quantile = args.top_entropy_quantile
        if self.use_liger_loss and self.top_entropy_quantile < 1.0:
            raise NotImplementedError(
                "Liger Kernels don't currently support masking token positions based on entropy."
            )
        if self.use_liger_loss and not self.importance_sampling_level == "token":
            raise NotImplementedError(
                "Liger Kernels currently only support token-level importance sampling. Please set"
                "`importance_sampling_level` to 'token'."
            )

        # Datasets
        self.shuffle_dataset = args.shuffle_dataset

        if (
            isinstance(train_dataset, IterableDataset)
            or isinstance(eval_dataset, IterableDataset)
            or (
                isinstance(eval_dataset, dict) and any(isinstance(ds, IterableDataset) for ds in eval_dataset.values())
            )
        ):
            # See https://github.com/huggingface/trl/issues/3213
            raise NotImplementedError(
                "Iterable datasets are not yet supported in GRPOTrainer. Please use a standard dataset instead."
            )

        # Multi-step
        self.num_iterations = args.num_iterations  # = 𝜇 in the GRPO paper
        self.epsilon_low = args.epsilon
        self.epsilon_high = args.epsilon_high if args.epsilon_high is not None else args.epsilon
        # Tracks the number of iterations [forward + backward passes], including those within a grad accum cycle
        self._step = 0
        # Buffer the batch to reuse generated outputs across multiple updates. For more details, see
        # `_get_train_sampler` and `_prepare_inputs`.
        self._buffered_inputs = None

        # The trainer estimates the number of FLOPs [floating-point operations] using the number of elements in the
        # input tensor associated with the key "input_ids". However, in GRPO, the sampled data does not include the
        # "input_ids" key. Instead, the available keys is "prompt". As a result, the trainer issues the warning:
        # "Could not estimate the number of tokens of the input, floating-point operations will not be computed." To
        # suppress this warning, we set the "estimate_tokens" key in the model's "warnings_issued" dictionary to True.
        # This acts as a flag to indicate that the warning has already been issued.
        model.warnings_issued["estimate_tokens"] = True

        super().__init__(
            model=model,
            args=args,
            data_collator=identity,  # No data collation is needed in GRPO
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            processing_class=processing_class,
            callbacks=callbacks,
            optimizers=optimizers,
            # In Trainer, `training_step` scales the loss by `gradient_accumulation_steps` only if `compute_loss_func`
            # is None. For DAPO, loss scaling instead depends on the total number of completions tokens across the
            # global accumulated batch. To control scaling ourselves, we must disable Trainer’s built-in scaling. The
            # simplest [though a bit hacky] way is to set `compute_loss_func` to any non-None value, which bypasses
            # that behavior without rewriting `training_step`.
            compute_loss_func="non-None value to disable scaling",
        )

        # Reference model
        self.beta = args.beta
        if self.beta == 0.0:
            # If beta is 0.0, the reference model is not needed
            self.ref_model = None
        elif is_peft_model(model):
            # If PEFT is used, the reference model is not needed since the adapter can be disabled
            # to revert to the initial model.
            self.ref_model = None
        else:
            # For deepspeed, fsdp or non-distributed models, create a reference model from scratch
            config = AutoConfig.from_pretrained(model_id)
            architecture = getattr(transformers, config.architectures[0])
            self.ref_model = architecture.from_pretrained(model_id, **model_init_kwargs)

        # Disable dropout in the models
        if args.disable_dropout:
            disable_dropout_in_model(model)
            if self.ref_model is not None:
                disable_dropout_in_model(self.ref_model)

        # Liger loss
        if self.use_liger_loss:
            if not is_liger_kernel_available():
                raise ImportError(
                    "Liger is required to use `liger_loss` as the GRPO loss. Run `pip install liger-kernel`."
                )
            # redirect the model.module forward to the model forward to ensure pre-forward hooks are called
            self._forward_redirection = _ForwardRedirection()

            self.liger_grpo_loss = LigerFusedLinearGRPOLoss(
                beta=self.beta,
                epsilon_low=self.epsilon_low,
                epsilon_high=self.epsilon_high,
                temperature=self.temperature,
                use_ref_model=self.beta != 0.0,
                loss_type=self.loss_type,
                max_completion_length=self.max_completion_length,
            )

        # Initialize the metrics
        self._metrics = {"train": defaultdict(list), "eval": defaultdict(list)}
        self._total_train_tokens = 0
        self.log_completions = args.log_completions
        self.wandb_log_unique_prompts = args.wandb_log_unique_prompts
        self.num_completions_to_print = args.num_completions_to_print
        # Keep logs sized to the generation batch to record only outputs from the latest model update.
        self._logs = {
            "images": deque(maxlen=args.generation_batch_size),
            "prompt": deque(maxlen=args.generation_batch_size),
            "completion": deque(maxlen=args.generation_batch_size),
            "rewards": defaultdict(lambda: deque(maxlen=args.generation_batch_size)),
            "advantages": deque(maxlen=args.generation_batch_size),
        }

        # Ensure each process receives a unique seed to prevent duplicate completions when generating with
        # transformers if num_generations exceeds per_device_train_batch_size. We could skip it if we use vLLM, but
        # it's safer to set it in all cases.
        set_seed(args.seed, device_specific=True)

        if self.use_vllm:
            if not is_vllm_available():
                raise ImportError(
                    "vLLM is not available and `use_vllm` is set to True. Please install vLLM with "
                    "`pip install trl[vllm]` to use it."
                )

            if self.vllm_mode == "server":
                if self.accelerator.is_main_process:
                    if args.vllm_server_base_url is not None:
                        base_url = args.vllm_server_base_url
                    else:
                        base_url = f"http://{args.vllm_server_host}:{args.vllm_server_port}"
                    self.vllm_client = VLLMClient(base_url=base_url, connection_timeout=args.vllm_server_timeout)
                    self.vllm_client.init_communicator(device=torch.cuda.current_device())

            elif self.vllm_mode == "colocate":
                if not self.accelerator.num_processes % self.vllm_tensor_parallel_size == 0:
                    raise ValueError(
                        f"vllm_tensor_parallel_size ({self.vllm_tensor_parallel_size}) must divide world size "
                        f"({self.accelerator.num_processes}) evenly."
                    )

                if self.vllm_tensor_parallel_size > 1:
                    self.tp_group, _ = torch.distributed.new_subgroups_by_enumeration(
                        [
                            list(range(i * self.vllm_tensor_parallel_size, (i + 1) * self.vllm_tensor_parallel_size))
                            for i in range(self.accelerator.num_processes // self.vllm_tensor_parallel_size)
                        ]
                    )
                os.environ["RANK"] = str(self.accelerator.process_index)
                os.environ["LOCAL_RANK"] = str(self.accelerator.local_process_index)
                os.environ["WORLD_SIZE"] = str(self.accelerator.num_processes)
                ensure_master_addr_port()

                if self.max_prompt_length is not None and self.max_completion_length is not None:
                    max_model_len = self.max_prompt_length + self.max_completion_length
                else:
                    max_model_len = None
                if getattr(getattr(model, 'vllm_engine', None), 'shared_weights', False):
                    self.llm = model.vllm_engine
                else:
                    self.llm = LLM(
                    model=model.name_or_path,
                    tensor_parallel_size=args.vllm_tensor_parallel_size,
                    gpu_memory_utilization=self.vllm_gpu_memory_utilization,
                    max_num_seqs=self.args.per_device_train_batch_size
                    * self.vllm_tensor_parallel_size
                    * self.args.steps_per_generation,
                    max_model_len=max_model_len,
                    distributed_executor_backend="external_launcher",
                    seed=self.accelerator.process_index // self.vllm_tensor_parallel_size,
                    max_num_batched_tokens=4096,
                    model_impl=self.args.vllm_model_impl,
                    enable_sleep_mode=self.args.vllm_enable_sleep_mode,
                    logprobs_mode="processed_logprobs",
                )
                if self.args.vllm_enable_sleep_mode:
                    self.llm.sleep(level=1)
            else:
                raise ValueError(f"vllm_mode must be either 'server' or 'colocate', got '{self.vllm_mode}'.")
            self.guided_decoding_regex = args.vllm_guided_decoding_regex

            self._last_loaded_step = -1
            self.accelerator.wait_for_everyone()
        else:
            generation_kwargs = {
                "max_new_tokens": self.max_completion_length,
                "do_sample": True,
                "pad_token_id": tokenizer.pad_token_id,
                "bos_token_id": tokenizer.bos_token_id,
                "eos_token_id": tokenizer.eos_token_id,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "top_k": self.top_k,
                "min_p": self.min_p,
                "repetition_penalty": self.repetition_penalty,
                "cache_implementation": args.cache_implementation,
            }
            if args.generation_kwargs is not None:
                generation_kwargs.update(args.generation_kwargs)
            self.generation_config = GenerationConfig(**generation_kwargs)

        # Gradient accumulation requires scaled loss. Normally, loss scaling in the parent class depends on whether the
        # model accepts loss-related kwargs. Since we compute our own loss, this check is irrelevant. We set
        # self.model_accepts_loss_kwargs to False to enable scaling.
        self.model_accepts_loss_kwargs = False

        # Add tags to the model
        self.model.add_model_tags(self._tag_names)

        if self.ref_model is not None:
            if self.is_deepspeed_enabled:
                self.ref_model = prepare_deepspeed(self.ref_model, self.accelerator)
            elif self.is_fsdp_enabled:
                self.ref_model = prepare_fsdp(self.ref_model, self.accelerator)
            else:
                self.ref_model = self.accelerator.prepare_model(self.ref_model, evaluation_mode=True)

        if args.sync_ref_model:
            self.add_callback(SyncRefModelCallback(ref_model=self.ref_model, accelerator=self.accelerator))

        for i, reward_func in enumerate(self.reward_funcs):
            if isinstance(reward_func, PreTrainedModel):
                if self.is_deepspeed_enabled:
                    self.reward_funcs[i] = prepare_deepspeed(reward_func, self.accelerator)
                else:
                    # set device placement to True to make `prepare_model` move `reward_func` to device when using fsdp
                    self.reward_funcs[i] = self.accelerator.prepare_model(
                        reward_func, evaluation_mode=True, device_placement=True
                    )

    def _set_signature_columns_if_needed(self):
        # If `self.args.remove_unused_columns` is True, non-signature columns are removed.
        # By default, this method sets `self._signature_columns` to the model's expected inputs.
        # In GRPOTrainer, we preprocess data, so using the model's signature columns doesn't work.
        # Instead, we set them to the columns expected by the `training_step` method, hence the override.
        if self._signature_columns is None:
            self._signature_columns = ["prompt", "image", "images"]

    # This method overrides `Trainer.get_train_dataloader` to support our custom batching strategy.
    # Instead of returning a standard per-step batch (i.e., `per_device_batch_size), our dataloader loads an
    # *generation* batch (i.e., `per_device_batch_size × steps_per_generation`). This allows us to generate completions
    # once every steps_per_generation step—rather than once per accumulation step—which is significantly more
    # efficient. The only change from the original implementation is multiplying the batch size by
    # `steps_per_generation`. Thus, `_prepare_inputs` is called with this *generation* batch, and it handles the
    # splitting internally.
    # Maintenance note: This method is a copy-paste of the original `Trainer.get_train_dataloader` with only one line
    # modification. As a result, some parts of the method aren't relevant to GRPO, but we keep them to stay one line
    # apart from the super method, ensuring easier maintenance in the future.
    def get_train_dataloader(self):
        if self.train_dataset is None:
            raise ValueError("Trainer: training requires a train_dataset.")

        train_dataset = self.train_dataset
        data_collator = self.data_collator
        if is_datasets_available() and isinstance(train_dataset, datasets.Dataset):
            train_dataset = self._remove_unused_columns(train_dataset, description="training")
        else:
            data_collator = self._get_collator_with_removed_columns(data_collator, description="training")

        dataloader_params = {
            "batch_size": self._train_batch_size * self.args.steps_per_generation,  # < this is the change
            "collate_fn": data_collator,
            "num_workers": self.args.dataloader_num_workers,
            "pin_memory": self.args.dataloader_pin_memory,
            "persistent_workers": self.args.dataloader_persistent_workers,
        }

        if not isinstance(train_dataset, torch.utils.data.IterableDataset):
            dataloader_params["sampler"] = self._get_train_sampler()
            dataloader_params["drop_last"] = self.args.dataloader_drop_last
            dataloader_params["worker_init_fn"] = partial(
                seed_worker, num_workers=self.args.dataloader_num_workers, rank=self.args.process_index
            )

            dataloader_params["prefetch_factor"] = self.args.dataloader_prefetch_factor

        return self.accelerator.prepare(DataLoader(train_dataset, **dataloader_params))

    def _get_train_sampler(self, dataset: Optional[Dataset] = None) -> Sampler:
        # Returns a sampler that
        # 1. ensures each prompt is repeated across multiple processes. This guarantees that identical prompts are
        #    distributed to different GPUs, allowing rewards to be computed and normalized correctly within each prompt
        #    group. Using the same seed across processes ensures consistent prompt assignment, preventing discrepancies
        #    in group formation.
        # 2. repeats the batch multiple times to allow reusing generations across multiple updates. Refer to
        #    _prepare_inputs to see how the generations are stored and reused.

        # In the following figure, the values are the prompt indices. The first row shows the first sampled batch, the
        # second row shows the second sampled batch, and so on.
        #
        #                                      |   GPU 0  |   GPU 1  |
        #
        #                 global_step   step    <-───>  num_generations=2
        #                                       <-───────> per_device_train_batch_size=3
        #  grad_accum    ▲  ▲  0          0     0   0   1   1   2   2   <- Generate for the first `steps_per_generation` (prompts 0 to 11); store the completions; use the first slice to compute the loss
        #     =2         ▼  |  0          1     3   3   4   4   5   5   <- Take the stored generations and use the second slice to compute the loss
        #                   |
        #                   |  1          2     6   6   7   7   8   8   <- Take the stored generations and use the third slice to compute the loss
        #  steps_per_gen=4  ▼  1          3     9   9  10  10  11  11   <- Take the stored generations and use the fourth slice to compute the loss
        #
        #                      2          4    12  12  13  13  14  14   <- Generate for the second `steps_per_generation` (prompts 12 to 23); store the completions; use the first slice to compute the loss
        #                      2          5    15  15  16  16  17  17   <- Take the stored generations and use the second slice to compute the loss
        #                                          ...
        if dataset is None:
            dataset = self.train_dataset
        return RepeatSampler(
            data_source=dataset,
            mini_repeat_count=self.num_generations,
            batch_size=self.args.generation_batch_size // self.num_generations,
            repeat_count=self.num_iterations * self.args.steps_per_generation,
            shuffle=self.shuffle_dataset,
            seed=self.args.seed,
        )

    def _get_eval_sampler(self, eval_dataset) -> Sampler:
        # See _get_train_sampler for an explanation of the sampler.
        return RepeatSampler(
            data_source=eval_dataset,
            mini_repeat_count=self.num_generations,
            seed=self.args.seed,
        )

    @profiling_decorator
    def _get_last_hidden_state(
        self,
        unwrapped_model,
        input_ids,
        attention_mask,
        logits_to_keep,
        pixel_values=None,
        image_grid_thw=None,
        pixel_attention_mask=None,
        image_sizes=None,
    ):
        if is_peft_model(unwrapped_model):
            unwrapped_model = unwrapped_model.base_model.model

        # Build model inputs - check if the model supports logits_to_keep (some models and VLMs don't)
        model_inputs = {"input_ids": input_ids, "attention_mask": attention_mask}

        # For Qwen models:
        if image_grid_thw is not None and pixel_values is not None:
            model_inputs["image_grid_thw"] = image_grid_thw
        # For Gemma, SmolVLM2, LLaVa-Next etc.:
        if pixel_values is not None:
            model_inputs["pixel_values"] = pixel_values
        # For SmolVLM2
        if pixel_attention_mask is not None:
            model_inputs["pixel_attention_mask"] = pixel_attention_mask
        # For LLaVa-Next
        if image_sizes is not None:
            model_inputs["image_sizes"] = image_sizes

        # Only add logits_to_keep if the model supports it
        if "logits_to_keep" in self.model_kwarg_keys:
            # We add 1 to `logits_to_keep` because the last logits of the sequence is later excluded
            model_inputs["logits_to_keep"] = logits_to_keep + 1

        model_inputs["use_cache"] = False  # only used in generation; set False to suppress warnings

        last_hidden_state = unwrapped_model.model(**model_inputs).last_hidden_state
        # Exclude the last value: it corresponds to the next token pred
        last_hidden_state = last_hidden_state[:, :-1, :]  # (B, L-1, H)
        # Only keep the last logits_to_keep. For model that support logits_to_keep, this is a no-op.
        last_hidden_state = last_hidden_state[:, -logits_to_keep:, :]  # (B, logits_to_keep, H)
        return last_hidden_state

    def get_high_entropy_mask(self, entropies: torch.Tensor, mask: torch.Tensor, threshold: float) -> torch.Tensor:
        """
        Returns a binary mask identifying tokens whose entropy exceeds a given quantile threshold.

        Args:
            entropies (`torch.Tensor`):
                Tensor of shape (batch_size, seq_len) with per-token entropy values.
            mask (`torch.Tensor`):
                Binary mask of the same shape as `entropies`, where `1` indicates valid tokens and `0` padding.
            threshold (`float`):
                Quantile threshold between `0.0` and `1.0` to select high-entropy tokens.

        Returns:
            `torch.Tensor`:
                Boolean mask of shape (batch_size, seq_len), where `True` indicates tokens with entropy >= threshold
                and `False` otherwise.
        """
        local = entropies[mask.bool()].float()

        # Use a negative pad_value as a sentinel because entropy values are always >= 0.
        # This guarantees that the sentinel cannot collide with any real entropy value.
        pad_value = -1e9

        # Pad across processes so that every rank has the same tensor length
        padded = self.accelerator.pad_across_processes(local, dim=0, pad_index=pad_value)
        gathered = self.accelerator.gather(padded)

        # Drop sentinel values (safe because no entropy can be negative)
        gathered = gathered[gathered != pad_value]

        if gathered.numel() == 0:
            return torch.zeros_like(entropies, dtype=torch.bool)

        entropy_threshold = torch.quantile(gathered, threshold)
        masked_entropies = entropies * mask.float()
        entropy_mask = masked_entropies >= entropy_threshold
        return entropy_mask & mask.bool()  # ensure padding tokens are always masked out

    def _get_per_token_logps_and_entropies(
        self,
        model,
        input_ids,
        attention_mask,
        logits_to_keep,
        batch_size = None,
        compute_entropy = False,
        compute_efficient = False,
        *args,
        **kwargs,
    ):
        # All Unsloth code here in this function is licensed under AGPL3
        # if True: # os.environ.get('UNSLOTH_USE_NEW_MODEL', '0') == '0':
        #     return None, None  # logps, entropies Unsloth efficient GRPO
        if compute_efficient:
            return None, None
        else:
            _unsloth_grpo_autocast(self)

            compute_aux_loss = kwargs.get("compute_aux_loss", None)

            pixel_values, image_grid_thw = (
                kwargs.get("pixel_values", None),
                kwargs.get("image_grid_thw", None),
            )
            pixel_attention_mask, image_sizes = (
                kwargs.get("pixel_attention_mask", None),
                kwargs.get("image_sizes", None),
            )
            num_images = kwargs.get("num_images", None)
            # Transformers 5.x needs token_type_ids/mm_token_type_ids for some vision models
            token_type_ids = kwargs.get("token_type_ids", None)
            mm_token_type_ids = kwargs.get("mm_token_type_ids", None)
            if mm_token_type_ids is not None or image_grid_thw is not None:
                mm_token_type_ids = _unsloth_fix_mm_token_type_ids(
                    self.processing_class, input_ids, mm_token_type_ids
                )

            unwrapped_model = self.accelerator.unwrap_model(model, keep_fp32_wrapper = False)

            lm_head = self.model.get_output_embeddings().weight

            # Size on the dtype the forward actually runs in: with autocast off that
            # is the model's own dtype, float32 or bfloat16 depending on the load.
            forward_dtype = (
                self._autocast_dtype if getattr(self, "_autocast_enabled", True) else lm_head.dtype
            )
            dtype_bytes = 16 if forward_dtype in [torch.float16, torch.bfloat16] else 32
            total_rows = input_ids.shape[0]
            seq_len = input_ids.shape[1]
            hidden_dim = lm_head.shape[1]
            vocab_dim = lm_head.shape[0]

            if self.args.unsloth_grpo_mini_batch is None:
                B, multiplier = autotune_batch_and_chunks(
                    total_rows,
                    seq_len,
                    hidden_dim,
                    vocab_dim,
                    dtype_bytes,
                    self.args.unsloth_logit_chunk_multiplier,
                )
                B = total_rows // B
            else:
                B = self.args.unsloth_grpo_mini_batch

                if self.args.unsloth_logit_chunk_multiplier is None:
                    multiplier = max(4, seq_len // 4096)
                else:
                    multiplier = self.args.unsloth_logit_chunk_multiplier

            all_logprobs_list = []
            if pixel_values is None:
                left_pad_tokens_per_prompt = calculate_pad_tokens_in_prompt(
                    input_ids, logits_to_keep, self.processing_class.pad_token_id
                )
                max_left_pad = torch.max(left_pad_tokens_per_prompt).item()
                input_ids = left_pack_padding(input_ids, self.processing_class.pad_token_id)
                attention_mask = input_ids != self.processing_class.pad_token_id
                attention_mask = attention_mask.to(attention_mask.dtype)
            else:
                max_left_pad = 0

            def slice_sample_axis(value, start, end):
                if value is None:
                    return None
                return value[start:end]

            import math

            total_samples = input_ids.shape[0]
            batch_size = math.ceil(total_samples / B)
            if isinstance(num_images, torch.Tensor):
                num_images = num_images.detach().cpu().reshape(-1).tolist()
            if image_grid_thw is not None and pixel_values is not None and num_images is not None:
                rows_per_image = image_grid_thw.prod(dim = -1)
                rows_per_sample = torch.split(rows_per_image, num_images)
                rows_per_sample = torch.stack([s.sum() for s in rows_per_sample])
                # why: cum_rows is indexed via .item() inside the per-chunk loop;
                # keeping it on CPU avoids per-iteration GPU->CPU sync.
                cum_rows = torch.cat(
                    [
                        torch.tensor([0], device = rows_per_sample.device),
                        rows_per_sample.cumsum(0),
                    ]
                ).cpu()
                cum_imgs = torch.tensor([0] + num_images).cumsum(0)
            else:
                cum_rows = None
                cum_imgs = None

            def _first_dim_len(value):
                if value is None:
                    return None
                if hasattr(value, "shape"):
                    return value.shape[0]
                try:
                    return len(value)
                except TypeError:
                    return None

            total_images = sum(num_images) if num_images is not None else None
            _image_sizes_n = _first_dim_len(image_sizes)

            input_ids_chunks = []
            attention_mask_chunks = []
            pixel_values_chunks = []
            image_grid_thw_chunks = []
            pixel_attention_mask_chunks = []
            image_sizes_chunks = []
            token_type_ids_chunks = []
            mm_token_type_ids_chunks = []

            current_pixel_idx = 0
            # TRL 0.23.0 batching logic
            for start in range(0, total_samples, batch_size):
                end = min(start + batch_size, total_samples)

                input_ids_chunks.append(input_ids[start:end])
                attention_mask_chunks.append(attention_mask[start:end])
                token_type_ids_chunks.append(slice_sample_axis(token_type_ids, start, end))
                mm_token_type_ids_chunks.append(slice_sample_axis(mm_token_type_ids, start, end))

                if image_grid_thw is not None and pixel_values is not None:
                    if num_images is None:
                        grid_slice = image_grid_thw[start:end]
                        batch_pixel_count = grid_slice.prod(dim = -1).sum().item()
                        start_pixel_idx = current_pixel_idx
                        end_pixel_idx = current_pixel_idx + batch_pixel_count
                        current_pixel_idx = end_pixel_idx
                        img_start = img_end = None
                    else:
                        start_pixel_idx = cum_rows[start].item()
                        end_pixel_idx = cum_rows[end].item()
                        img_start = cum_imgs[start].item()
                        img_end = cum_imgs[end].item()
                        grid_slice = image_grid_thw[img_start:img_end]
                    image_grid_thw_chunks.append(grid_slice)

                    pixel_values_chunks.append(pixel_values[start_pixel_idx:end_pixel_idx])

                    if image_sizes is None:
                        image_sizes_chunks.append(None)
                    elif (
                        num_images is not None
                        and _image_sizes_n == total_images
                        and img_start is not None
                    ):
                        image_sizes_chunks.append(image_sizes[img_start:img_end])
                    else:
                        image_sizes_chunks.append(slice_sample_axis(image_sizes, start, end))

                    if pixel_attention_mask is None:
                        pixel_attention_mask_chunks.append(None)
                    elif (
                        num_images is not None
                        and img_start is not None
                        and pixel_attention_mask.shape[0] == image_grid_thw.shape[0]
                    ):
                        pixel_attention_mask_chunks.append(pixel_attention_mask[img_start:img_end])
                    elif (
                        pixel_attention_mask.shape[0] == pixel_values.shape[0]
                        and pixel_attention_mask.shape[0] != input_ids.shape[0]
                    ):
                        pixel_attention_mask_chunks.append(
                            pixel_attention_mask[start_pixel_idx:end_pixel_idx]
                        )
                    else:
                        pixel_attention_mask_chunks.append(pixel_attention_mask[start:end])

                else:
                    pixel_values_chunks.append(None)
                    image_grid_thw_chunks.append(None)
                    pixel_attention_mask_chunks.append(None)
                    image_sizes_chunks.append(slice_sample_axis(image_sizes, start, end))

            temperature = self.temperature
            model_config = _unsloth_get_model_config(model)
            logit_softcapping = _unsloth_get_final_logit_softcapping(model)
            logit_scale_multiply = getattr(model_config, "logit_scale", 0)
            if logit_scale_multiply is None:
                logit_scale_multiply = 0
            logit_scale_divide = getattr(model_config, "logits_scaling", 0)
            if logit_scale_divide is None:
                logit_scale_divide = 0

            zipped_inputs = zip(
                input_ids_chunks,
                attention_mask_chunks,
                pixel_values_chunks,
                image_grid_thw_chunks,
                pixel_attention_mask_chunks,
                image_sizes_chunks,
                token_type_ids_chunks,
                mm_token_type_ids_chunks,
            )
            os.environ["UNSLOTH_RETURN_HIDDEN_STATES"] = "1"

            # ---- Sequence packing (default-on; disable with UNSLOTH_GRPO_SEQ_PACKING=0) ----
            # One varlen [1, sum L] forward replaces the padded [B, Lmax] loop (also fixes the
            # left-pad RoPE error). Self-verified against the per-row forward, re-checked as T
            # grows; falls back if a backend ignores packed_seq_lengths.
            logprobs = None

            # ---- PrefixGrouper (GRPO shared-prompt dedup; default ON, exact + self-verified) ----
            # G completions per prompt share the prefix; the packed path forwards it G times,
            # PrefixGrouper stores it once (FlexAttention shared-prefix mask), cutting the trunk
            # forward from G*(P+R) to P+G*R tokens. Gated by UNSLOTH_GRPO_PREFIX_GROUPER (needs
            # seq-packing), tok_r auto-gate, and first-use self-verify vs the packed path
            # (mismatch => fall back + mark unsafe), so a mask/isolation regression cannot ship
            # silently. When off / ungrouped / unverified, the packed path below runs as before.
            _pg_result = None
            _pg_use = False
            _pg_skip_pk = False  # once a shape is PG-verified, skip the full-row forward
            _pg_forward_fn = None  # deferred PG forward (runs at the verify site below)
            _pg_num_gen = getattr(self, "num_generations", None)
            # Env gate hoisted to module level (mirrored via RL_PRE_ITEMS). Skip PG under vLLM
            # (fast_inference=True): the rollout dominates the step, so PG saves little and its
            # first-use self-verify is net overhead.
            _pg_engage = (
                UNSLOTH_GRPO_PREFIX_GROUPER_ON
                and not getattr(self, "use_vllm", False)
                and not getattr(unwrapped_model, "_unsloth_prefix_grouper_nograd_disabled", False)
            )
            if _pg_engage:
                try:
                    # Skip softcap models (the flex kernel never applies attn_logit_softcapping)
                    # and hybrid SSM / MoE models: only the threaded attention forwards get the
                    # shared-prefix isolation, so a Mamba or MoE decoder that does not forward
                    # prefix_seg_info would leak suffixes across completions. PG also rides on
                    # sequence packing, so it needs the same zoo masked-column guard.
                    _pg_cfg = getattr(unwrapped_model, "config", None)
                    _pg_engage = (
                        _pg_enabled_fn()
                        and UNSLOTH_ZOO_HAS_MASKED_COL_GUARD
                        and pixel_values is None
                        and token_type_ids is None
                        and mm_token_type_ids is None
                        and _pg_num_gen is not None
                        and _pg_num_gen >= 2
                        and not getattr(_pg_cfg, "attn_logit_softcapping", None)
                        # normal backends apply config.attention_dropout in training; the flex
                        # path is deterministic, so skip PG when it is set.
                        and not getattr(_pg_cfg, "attention_dropout", 0)
                        and not any(
                            getattr(_pg_cfg, _pg_a, None) is not None
                            for _pg_a in (
                                "mamba_d_ssm",
                                "mamba_d_state",
                                "mamba_expand",
                                "num_experts",
                                "num_local_experts",
                                "n_routed_experts",
                                "moe_intermediate_size",
                            )
                        )
                    )
                except Exception:
                    _pg_engage = False
            if _pg_engage:
                try:
                    _pg_pad = self.processing_class.pad_token_id
                    # cap the PG span (P+max(R)) at the sliding window, like the packed _pk_sw guard.
                    _pg_sw = getattr(
                        getattr(unwrapped_model, "config", None), "sliding_window", None
                    )
                    if not (isinstance(_pg_sw, int) and _pg_sw > 0):
                        _pg_sw = None
                    _pg_layout = _pg_build_layout(
                        input_ids,
                        logits_to_keep,
                        _pg_pad,
                        _pg_num_gen,
                        left_pad_tokens_per_prompt,
                        max_segment_cap = _pg_sw,
                    )
                    _pg_unsafe = getattr(
                        unwrapped_model, "_unsloth_prefix_grouper_nograd_unsafe", None
                    )
                    if _pg_unsafe is None:
                        _pg_unsafe = set()
                    if _pg_layout is not None and _pg_layout.signature not in _pg_unsafe:
                        _pg_sig = _pg_layout.signature
                        _pg_verified = getattr(
                            unwrapped_model, "_unsloth_prefix_grouper_nograd_verified", None
                        )
                        if _pg_verified is None:
                            _pg_verified = set()
                        _pg_chunks = max(1, total_rows * multiplier)

                        def _pg_run_forward(_pg_layout = _pg_layout, _pg_chunks = _pg_chunks):
                            with _get_inference_mode_context_manager(model):
                                with torch.amp.autocast(
                                    device_type = "cuda",
                                    dtype = self._autocast_dtype,
                                    enabled = getattr(self, "_autocast_enabled", True),
                                ):
                                    _pg_hidden = unwrapped_model(
                                        input_ids = _pg_layout.flat_ids,
                                        position_ids = _pg_layout.position_ids,
                                        prefix_seg_info = _pg_layout.prefix_seg_info,
                                        use_cache = False,
                                    ).logits
                                    _pg_r = _pg_layout.extract_logps(
                                        _pg_hidden,
                                        lm_head,
                                        chunked_hidden_states_selective_log_softmax,
                                        _pg_chunks,
                                        logit_scale_multiply,
                                        logit_scale_divide,
                                        logit_softcapping,
                                        temperature,
                                    )
                                    _pg_hidden = None  # release before any verify forward
                            device_synchronize()
                            # clip to the loss window [B, logits_to_keep+max_left_pad]
                            _pg_w = logits_to_keep + max_left_pad
                            if _pg_r.shape[1] > _pg_w:
                                _pg_r = _pg_r[:, -_pg_w:]
                            return _pg_r

                        # trust only within the verified envelope: re-verify when T or the
                        # longest segment grows, like the packed path
                        _pg_T = int(_pg_layout.flat_ids.shape[1])
                        _pg_maxseg = int(_pg_layout.position_ids.max()) + 1
                        _pg_env = (
                            _pg_verified.get(_pg_sig) if isinstance(_pg_verified, dict) else None
                        )
                        if (not _pg_verify_on()) or (
                            _pg_env is not None and _pg_T <= _pg_env[0] and _pg_maxseg <= _pg_env[1]
                        ):
                            # trusted shape: run PG now and skip the full-row forward below
                            _pg_result = _pg_run_forward()
                            _pg_use = True
                            _pg_skip_pk = True
                        else:
                            # unverified shape: defer the forward until the packed reference
                            # exists (verify site below), so a declined packed path never wastes
                            # a whole-batch PG forward
                            _pg_forward_fn = _pg_run_forward
                except Exception as _pg_err:
                    _pg_result = None
                    _pg_use = False
                    _pg_skip_pk = False
                    _pg_forward_fn = None
                    # A FlexAttention/Triton compile failure or OOM here is GPU-wide, not
                    # layout-specific, so retrying the same PG forward every step just re-pays
                    # the failure. Persistently disable PG (mirrors the seq-packing handler
                    # setting _unsloth_seq_packing_nograd_ok = False); the packed/padded path
                    # below still produces the exact result.
                    unwrapped_model._unsloth_prefix_grouper_nograd_disabled = True
                    if isinstance(_pg_err, torch.cuda.OutOfMemoryError):
                        torch.cuda.empty_cache()
                    os.environ["UNSLOTH_RETURN_HIDDEN_STATES"] = "1"
                    if UNSLOTH_ENABLE_LOGGING:
                        print(
                            f"[Unsloth] GRPO PrefixGrouper (no-grad) disabled (fell back to packed): {_pg_err!r}",
                            flush = True,
                        )

            # ---- Sequence packing (default-on; disable with UNSLOTH_GRPO_SEQ_PACKING=0) ----
            # One varlen [1, sum L] block-diagonal forward replaces the padded [B, Lmax] loop
            # (exact per-row result; also fixes the padded path's left-pad RoPE error).
            # Self-verified vs the per-row forward, re-checked as T grows; falls back if a
            # backend ignores packed_seq_lengths. lm_head runs on completion positions only.
            _pk_result = None
            _pk_use = False
            _pk_enabled = UNSLOTH_GRPO_SEQ_PACKING_ON
            # Without zoo#840's masked-column guard, zeroed prompt/pad columns turn NaN in exp().
            _pk_enabled = _pk_enabled and UNSLOTH_ZOO_HAS_MASKED_COL_GUARD
            _pk_ok = getattr(unwrapped_model, "_unsloth_seq_packing_nograd_ok", None)
            if (
                _pk_enabled
                and not _pg_skip_pk
                and pixel_values is None
                and token_type_ids is None
                and mm_token_type_ids is None
                and _pk_ok is not False
            ):
                try:
                    _pk_pad = self.processing_class.pad_token_id
                    _pk_keep = input_ids != _pk_pad
                    _pk_len = _pk_keep.sum(dim = 1)
                    _pk_len_cpu = _pk_len.tolist()  # single GPU->CPU sync, reused below
                    _pk_nz_cpu = [_n for _n in _pk_len_cpu if _n > 0]
                    _pk_flat = input_ids[_pk_keep].unsqueeze(0)
                    _pk_T = _pk_flat.shape[1]
                    _pk_L = input_ids.shape[1]
                    _pk_W = logits_to_keep + max_left_pad
                    _pk_maxseg = max(_pk_nz_cpu) if _pk_nz_cpu else 0
                    # sliding-window models lose the per-sequence local window in a packed stream
                    _pk_sw = getattr(
                        getattr(unwrapped_model, "config", None), "sliding_window", None
                    )
                    _pk_sw_ok = not (isinstance(_pk_sw, int) and _pk_sw > 0 and _pk_maxseg > _pk_sw)
                    # per-row completion mask (same as the loss); prompt-only rows count as inactive
                    _pk_cmask = create_completion_attention_mask(
                        input_ids[:, -_pk_W:], left_pad_tokens_per_prompt, max_left_pad, _pk_pad
                    )
                    _pk_active = int(_pk_cmask.any(dim = 1).sum())
                    # skip the packed forward entirely at known-unsafe lengths (avoids a wasted pass / OOM)
                    _pk_unsafe = getattr(
                        unwrapped_model, "_unsloth_seq_packing_nograd_unsafe_T", None
                    )
                    # cap the flattened forward at one padded [batch_size, seq_len] mini-batch's
                    # token budget; anything larger uses the chunked padded loop
                    _pk_cap = batch_size * seq_len
                    if (
                        _pk_T >= 2
                        and _pk_T <= _pk_cap
                        and len(_pk_nz_cpu) > 0
                        and _pk_sw_ok
                        and not (_pk_unsafe is not None and _pk_T >= _pk_unsafe)
                        and (_pk_ok is True or _pk_active >= 2)
                    ):
                        # reset 0-based position_ids per segment
                        _pk_pos = (_pk_keep.cumsum(dim = 1) - 1)[_pk_keep].unsqueeze(0)
                        _pk_chunks = max(1, total_rows * multiplier)
                        _pk_nz_idx = _pk_keep.nonzero(
                            as_tuple = False
                        )  # [T, 2] = (row, col), row-major
                        _pk_within = _pk_nz_idx[1:, 0] == _pk_nz_idx[:-1, 0]  # [T-1]
                        # per-row completion start after left-packing (matches create_completion_attention_mask)
                        _pk_cstart = (_pk_L - logits_to_keep) - left_pad_tokens_per_prompt  # [rows]
                        _pk_ctgt = (_pk_nz_idx[1:, 1] >= _pk_cstart[_pk_nz_idx[1:, 0]]) & _pk_within
                        with _get_inference_mode_context_manager(model):
                            with torch.amp.autocast(
                                device_type = "cuda",
                                dtype = self._autocast_dtype,
                                enabled = getattr(self, "_autocast_enabled", True),
                            ):
                                # use_cache=False: a KV cache silently disables varlen packing
                                _pk_hidden = unwrapped_model(
                                    input_ids = _pk_flat,
                                    position_ids = _pk_pos,
                                    packed_seq_lengths = torch.tensor(
                                        _pk_nz_cpu, dtype = torch.int32, device = input_ids.device
                                    ),
                                    use_cache = False,
                                ).logits
                                _pk_out = _pk_hidden[0, :-1, :][_pk_ctgt].unsqueeze(0)
                                _pk_ids = _pk_flat[0, 1:][_pk_ctgt].unsqueeze(0)
                                # Guard: check if model returned hidden states or logits
                                if _unsloth_grpo_returns_hidden_states(
                                    unwrapped_model, _pk_out, lm_head
                                ):
                                    _pk_sel = chunked_hidden_states_selective_log_softmax(
                                        _pk_out,
                                        lm_head,
                                        _pk_ids,
                                        _pk_chunks,
                                        logit_scale_multiply,
                                        logit_scale_divide,
                                        logit_softcapping,
                                        temperature,
                                    )[0]
                                else:
                                    # Model returned logits directly - scaling/softcapping already applied by model forward
                                    _pk_sel = chunked_selective_log_softmax(
                                        _pk_out,
                                        _pk_ids,
                                        temperature,
                                        _pk_chunks,
                                    )[0]
                        # GPT-OSS offload race guard (matches the padded loop)
                        device_synchronize()
                        # scatter each logprob back to its (row, col) so [:, -_pk_W:] matches padded
                        _pk_tgt = (_pk_nz_idx[1:, 0] * _pk_L + _pk_nz_idx[1:, 1])[_pk_ctgt]
                        _pk_result = (
                            torch.zeros(
                                total_rows * _pk_L,
                                dtype = torch.float32,
                                device = input_ids.device,
                            )
                            .index_put((_pk_tgt,), _pk_sel.to(torch.float32))
                            .view(total_rows, _pk_L)[:, -_pk_W:]
                        )
                        # re-verify when T or the longest segment grows past what was verified
                        # (a LongRoPE cache switch can change the result)
                        _pk_vT = int(
                            getattr(unwrapped_model, "_unsloth_seq_packing_nograd_verified_T", 0)
                        )
                        _pk_vS = int(
                            getattr(unwrapped_model, "_unsloth_seq_packing_nograd_verified_seg", 0)
                        )
                        # debug: hand-edit this condition to force re-verify every step
                        if _pk_ok is True and _pk_T <= _pk_vT and _pk_maxseg <= _pk_vS:
                            _pk_use = True  # already verified for this shape
                        else:
                            # verify against the per-row forward (ground truth)
                            _pk_ref = torch.zeros_like(_pk_result)
                            with _get_inference_mode_context_manager(model):
                                with torch.amp.autocast(
                                    device_type = "cuda",
                                    dtype = self._autocast_dtype,
                                    enabled = getattr(self, "_autocast_enabled", True),
                                ):
                                    for _pk_i in range(total_rows):
                                        _pk_ni = _pk_len_cpu[_pk_i]
                                        if _pk_ni < 2:
                                            continue
                                        _pk_rmask = _pk_keep[_pk_i]
                                        _pk_real = input_ids[_pk_i][_pk_rmask].unsqueeze(0)
                                        _pk_rpos = torch.arange(
                                            _pk_ni, device = input_ids.device
                                        ).unsqueeze(0)
                                        _pk_rh = unwrapped_model(
                                            input_ids = _pk_real,
                                            position_ids = _pk_rpos,
                                            use_cache = False,
                                        ).logits
                                        _pk_rout = _pk_rh[:, :-1, :]
                                        # Guard: check if model returned hidden states or logits
                                        if _unsloth_grpo_returns_hidden_states(
                                            unwrapped_model, _pk_rout, lm_head
                                        ):
                                            _pk_rsel = chunked_hidden_states_selective_log_softmax(
                                                _pk_rout,
                                                lm_head,
                                                _pk_real[:, 1:],
                                                1,
                                                logit_scale_multiply,
                                                logit_scale_divide,
                                                logit_softcapping,
                                                temperature,
                                            )[0]
                                        else:
                                            # Model returned logits directly - scaling/softcapping already applied by model forward
                                            _pk_rsel = chunked_selective_log_softmax(
                                                _pk_rout,
                                                _pk_real[:, 1:],
                                                temperature,
                                                1,
                                            )[0]
                                        _pk_rcols = _pk_rmask.nonzero(as_tuple = False).squeeze(1)[
                                            1:
                                        ] - (_pk_L - _pk_W)
                                        _pk_rkeep = _pk_rcols >= 0
                                        _pk_ref[_pk_i, _pk_rcols[_pk_rkeep]] = _pk_rsel[
                                            _pk_rkeep
                                        ].to(torch.float32)
                            device_synchronize()
                            # compare over the loss-mask region only
                            _pk_cm = _pk_cmask.float()
                            _pk_diff = float(((_pk_result - _pk_ref).abs() * _pk_cm).max())
                            if UNSLOTH_ENABLE_LOGGING:
                                print(
                                    f"[Unsloth] GRPO seq-packing (no-grad) verify: T={_pk_T} maxseg={_pk_maxseg} packed-vs-perrow max|d|={_pk_diff:.4f}",
                                    flush = True,
                                )
                            # kernel-noise floor ~0.25; cross-sample contamination is >= 2.4
                            if _pk_diff < 7e-1:
                                unwrapped_model._unsloth_seq_packing_nograd_ok = True
                                # widen the trusted shape only when >= 2 completion rows exercised
                                # cross-sample packing; single-row passes prove nothing
                                if _pk_active >= 2:
                                    unwrapped_model._unsloth_seq_packing_nograd_verified_T = max(
                                        _pk_vT, _pk_T
                                    )
                                    unwrapped_model._unsloth_seq_packing_nograd_verified_seg = max(
                                        _pk_vS, _pk_maxseg
                                    )
                                _pk_ok = True
                                _pk_use = True
                            else:
                                _pk_use = False
                                if _pk_diff >= 1.5:
                                    # contamination (attention ignores the packed mask): disable packing
                                    unwrapped_model._unsloth_seq_packing_nograd_ok = False
                                else:
                                    # likely a length boundary (LongRoPE): mark unsafe, keep smaller shapes
                                    unwrapped_model._unsloth_seq_packing_nograd_unsafe_T = (
                                        _pk_T if _pk_unsafe is None else min(_pk_unsafe, _pk_T)
                                    )
                                if UNSLOTH_ENABLE_LOGGING:
                                    print(
                                        f"[Unsloth] GRPO seq-packing (no-grad) fell back at T={_pk_T} (diff={_pk_diff:.3f})",
                                        flush = True,
                                    )
                except Exception as _pk_err:
                    # any failure: drop intermediates, use the padded loop, do not retry
                    _pk_hidden = None
                    _pk_sel = None
                    _pk_result = None
                    _pk_use = False
                    if isinstance(_pk_err, torch.cuda.OutOfMemoryError):
                        torch.cuda.empty_cache()
                    unwrapped_model._unsloth_seq_packing_nograd_ok = False
                    if UNSLOTH_ENABLE_LOGGING:
                        print(
                            f"[Unsloth] GRPO sequence-packing (no-grad) disabled (fell back to padded): {_pk_err!r}",
                            flush = True,
                        )
            # ---- PrefixGrouper first-use self-verify (no-grad) ----
            # Compare the untrusted PG result to the full-row packed result (itself verified vs
            # per-row) over the completion mask: < tol_ok -> trust the structure; >= TOL_KILL ->
            # unsafe forever; borderline -> fall back this shape.
            if _pg_forward_fn is not None and not _pg_use:
                if _pk_use and _pk_result is not None:
                    try:
                        # deferred PG forward, run only now that the packed reference exists
                        _pg_result = _pg_forward_fn()
                        _pg_W2 = logits_to_keep + max_left_pad
                        _pg_cm = create_completion_attention_mask(
                            input_ids[:, -_pg_W2:],
                            left_pad_tokens_per_prompt,
                            max_left_pad,
                            self.processing_class.pad_token_id,
                        ).float()
                        _pg_a = _pg_result[:, -_pg_W2:].float()
                        _pg_b = _pk_result[:, -_pg_W2:].float()
                        _pg_diff = float(((_pg_a - _pg_b).abs() * _pg_cm).max())
                        if UNSLOTH_ENABLE_LOGGING:
                            print(
                                f"[Unsloth] GRPO PrefixGrouper (no-grad) verify: sig={_pg_layout.signature} "
                                f"shared-prefix vs full-row-packed max|d|={_pg_diff:.4f}",
                                flush = True,
                            )
                        if _pg_diff < _pg_tol_ok():
                            _pg_v = getattr(
                                unwrapped_model, "_unsloth_prefix_grouper_nograd_verified", None
                            )
                            if not isinstance(_pg_v, dict):
                                _pg_v = {}
                            _pg_vT = int(_pg_layout.flat_ids.shape[1])
                            _pg_vS = int(_pg_layout.position_ids.max()) + 1
                            _pg_old = _pg_v.get(_pg_layout.signature, (0, 0))
                            _pg_v[_pg_layout.signature] = (
                                max(_pg_vT, _pg_old[0]),
                                max(_pg_vS, _pg_old[1]),
                            )
                            unwrapped_model._unsloth_prefix_grouper_nograd_verified = _pg_v
                            _pg_use = True
                        else:
                            _pg_u = getattr(
                                unwrapped_model, "_unsloth_prefix_grouper_nograd_unsafe", None
                            )
                            if _pg_u is None:
                                _pg_u = set()
                            if _pg_diff >= _PG_TOL_KILL:
                                _pg_u.add(_pg_layout.signature)
                                unwrapped_model._unsloth_prefix_grouper_nograd_unsafe = _pg_u
                            _pg_use = False
                    except Exception as _pg_err3:
                        _pg_result = None
                        _pg_use = False
                        if isinstance(_pg_err3, torch.cuda.OutOfMemoryError):
                            torch.cuda.empty_cache()
                        os.environ["UNSLOTH_RETURN_HIDDEN_STATES"] = "1"
                        if UNSLOTH_ENABLE_LOGGING:
                            print(
                                f"[Unsloth] GRPO PrefixGrouper (no-grad) verify failed (fell back to packed): {_pg_err3!r}",
                                flush = True,
                            )
                # else: no packed reference (packing off/failed) -> cannot verify; fall back.

            if _pg_use and _pg_result is not None:
                logprobs = _pg_result  # PrefixGrouper verified/trusted -> skip the loop
                zipped_inputs = []
            elif _pk_use and _pk_result is not None:
                logprobs = _pk_result  # verified -> skip the loop
                zipped_inputs = []
            else:
                # free packed intermediates before running the padded loop
                _pk_hidden = _pk_sel = _pk_result = _pk_ref = None

            with _get_inference_mode_context_manager(model):
                for (
                    input_ids_chunk,
                    attention_mask_chunk,
                    pixel_values_chunk,
                    image_grid_thw_chunk,
                    pixel_attention_mask_chunk,
                    image_sizes_chunk,
                    token_type_ids_chunk,
                    mm_token_type_ids_chunk,
                ) in zipped_inputs:
                    _extra_vision_kwargs = {}
                    if token_type_ids_chunk is not None:
                        _extra_vision_kwargs["token_type_ids"] = token_type_ids_chunk
                    if mm_token_type_ids_chunk is not None:
                        _extra_vision_kwargs["mm_token_type_ids"] = mm_token_type_ids_chunk
                    with torch.amp.autocast(
                        device_type = "cuda",
                        dtype = self._autocast_dtype,
                        enabled = getattr(self, "_autocast_enabled", True),
                    ):
                        if pixel_values is None:
                            outputs = unwrapped_model(
                                input_ids = input_ids_chunk,
                                attention_mask = attention_mask_chunk,
                                pixel_values = pixel_values_chunk,
                                image_grid_thw = image_grid_thw_chunk,
                                pixel_attention_mask = pixel_attention_mask_chunk,
                                image_sizes = image_sizes_chunk,
                                **_extra_vision_kwargs,
                            )

                            logits_chunk = outputs.logits
                            del outputs  # free hidden_states before chunked log-softmax

                            completion_input_ids_chunk = input_ids_chunk[
                                :, -(logits_to_keep + max_left_pad) :
                            ]
                            logits_chunk = logits_chunk[
                                :, -(logits_to_keep + max_left_pad + 1) :, :
                            ]
                            logits_chunk = logits_chunk[:, :-1, :]
                            # Guard: check if model returned hidden states or logits
                            if _unsloth_grpo_returns_hidden_states(
                                unwrapped_model, logits_chunk, lm_head
                            ):
                                logprobs_chunk = chunked_hidden_states_selective_log_softmax(
                                    logits_chunk,
                                    lm_head,
                                    completion_input_ids_chunk,
                                    chunks = input_ids_chunk.shape[0] * multiplier,
                                    logit_scale_multiply = logit_scale_multiply,
                                    logit_scale_divide = logit_scale_divide,
                                    logit_softcapping = logit_softcapping,
                                    temperature = temperature,
                                )
                            else:
                                # Model returned logits directly - scaling/softcapping already applied by model forward
                                logprobs_chunk = chunked_selective_log_softmax(
                                    logits_chunk,
                                    completion_input_ids_chunk,
                                    temperature,
                                    input_ids_chunk.shape[0] * multiplier,
                                )
                        else:
                            # Essentially, for VLMs we do not go via the optimized path in models/,
                            # so we don't encounter the Flash Attn left-padding issue.
                            outputs = unwrapped_model(
                                input_ids = input_ids_chunk,
                                attention_mask = attention_mask_chunk,
                                pixel_values = pixel_values_chunk,
                                image_grid_thw = image_grid_thw_chunk,
                                pixel_attention_mask = pixel_attention_mask_chunk,
                                image_sizes = image_sizes_chunk,
                                logits_to_keep = logits_to_keep + 1,
                                **_extra_vision_kwargs,
                            )

                            logits_chunk = outputs.logits
                            del outputs  # free hidden_states before chunked log-softmax

                            logits_chunk = logits_chunk[:, :-1, :]
                            completion_input_ids_chunk = input_ids_chunk[:, -logits_to_keep:]
                            # Guard: check if model returned hidden states or logits
                            if _unsloth_grpo_returns_hidden_states(
                                unwrapped_model, logits_chunk, lm_head
                            ):
                                logprobs_chunk = chunked_hidden_states_selective_log_softmax(
                                    logits_chunk,
                                    lm_head,
                                    completion_input_ids_chunk,
                                    chunks = input_ids_chunk.shape[0] * multiplier,
                                    logit_scale_multiply = logit_scale_multiply,
                                    logit_scale_divide = logit_scale_divide,
                                    logit_softcapping = logit_softcapping,
                                    temperature = temperature,
                                )
                            else:
                                # Model returned logits directly - scaling/softcapping already applied by model forward
                                logprobs_chunk = chunked_selective_log_softmax(
                                    logits_chunk,
                                    completion_input_ids_chunk,
                                    temperature,
                                )
                    # This is needed to avoid race conditions with GPT OSS offload_embbed=True
                    # However, it seems that this line does not slow down or disrupt models.
                    device_synchronize()
                    all_logprobs_list.append(logprobs_chunk)
                if logprobs is None:  # padded fallback when packing was not used
                    logprobs = torch.cat(all_logprobs_list, dim = 0)

                entropies = None

            os.environ["UNSLOTH_RETURN_HIDDEN_STATES"] = "0"
            # aux loss is unused: it is off by default (router_aux_loss_coef set to 0 in models/rl.py)
            # and explicit opt-in is rejected at trainer init, so this is always None (kept in the
            # return for TRL >= 1.7.0's 3-tuple contract).
            aux_loss = None
            return logprobs.detach(), entropies  # logps, entropies
            # input_ids = input_ids[:, -logits_to_keep:]
            # For transformers<=4.48, logits_to_keep argument isn't supported, so here we drop logits ourselves.
            # See https://github.com/huggingface/trl/issues/2770
            # logits = logits[:, -logits_to_keep:]
            # return logits
            # See https://huggingface.co/blog/the_n_implementation_details_of_rlhf_with_ppo#policy-training-implementation-details
            # logits = logits / self.temperature
            # logps = selective_log_softmax(logits, input_ids)

            # row_indices, col_indices = torch.where(logps < -20)

            # # Method 1: Check if tensors have elements
            # if len(row_indices) > 0 and len(col_indices) > 0:
            #     breakpoint()  # Breakpoint triggered here
            #     print("Found high values!")
            # return  logps #  compute logprobs for the input tokens

    def _fix_param_name_to_vllm(self, name, extra_prefixes: Optional[list[str]] = None):
        extra_prefixes = extra_prefixes or []
        prefixes = ["_checkpoint_wrapped_module."] + extra_prefixes
        for prefix in prefixes:
            name = name.replace(prefix, "")
        return name

    def _sync_fsdp1_params_to_vllm(self, module: nn.Module, prefix: str = "", visited=None):
        """Memory-efficient post-order traversal of FSDP modules to extract full parameters and sync with vLLM."""
        # For FSDP1, we need to recurse into children and also use summon_full_params
        if visited is None:
            visited = set()
        for child_name, child_module in module.named_children():
            child_prefix = f"{prefix}.{child_name}" if prefix else child_name
            self._sync_fsdp1_params_to_vllm(
                child_module, prefix=child_prefix, visited=visited
            )  # recurse into the child

        if isinstance(module, FSDP):
            with FSDP.summon_full_params(module, recurse=False, writeback=False):
                for param_name, param in module.named_parameters():
                    full_name = f"{prefix}.{param_name}" if prefix else param_name
                    full_name = self._fix_param_name_to_vllm(full_name, extra_prefixes=["_fsdp_wrapped_module."])

                    if full_name in visited:
                        continue  # skip FSDP subtrees already traversed
                    visited.add(full_name)

                    if self.vllm_mode == "server" and self.accelerator.is_main_process:
                        self.vllm_client.update_named_param(full_name, param.data)
                    elif self.vllm_mode == "colocate":

                        pass

                        pass

    def _sync_fsdp2_params_to_vllm(self, module: nn.Module):
        # For FSDP2, module already covers all parameters, so no need for recursion
        for name, param in module.items():
            if param.is_cpu:
                param = param.to(torch.device("cuda"))
            param = param.full_tensor()

            if self.vllm_mode == "server" and self.accelerator.is_main_process:
                self.vllm_client.update_named_param(name, param)
            elif self.vllm_mode == "colocate":

                pass

                pass

    def _move_model_to_vllm(self, *args, **kwargs):
        return None

    @profiling_decorator
    def _prepare_inputs(
        self, generation_batch: dict[str, Union[torch.Tensor, Any]]
    ) -> dict[str, Union[torch.Tensor, Any]]:
        # Prepares inputs for model training/evaluation by managing completion generation and batch handling.
        # During training:
        #   - Receives the local generation batch (Per-GPU batch size × steps per generation)
        #     from the modified training dataloader instead of the standard local batch
        #   - Generates completions once for the entire generation batch and splits it into batches of size
        #     `per_device_train_batch_size`
        #   - Buffers these completions and returns the appropriate slice for the current accumulation step
        #   - Optimizes by regenerating completions only periodically (every steps_per_generation * num_iterations)
        # During evaluation:
        #   - The input is treated as a standard local batch (no accumulation, no multiple iterations)
        #   - Completions are generated for each batch without buffering or reuse
        # Returns a single local batch in both cases.

        mode = "train" if self.model.training else "eval"
        if mode == "train":
            generate_every = self.args.steps_per_generation * self.num_iterations
            if self._step % generate_every == 0 or self._buffered_inputs is None:
                # self._buffered_inputs=None can occur when resuming from a checkpoint
                generation_batch = self._generate_and_score_completions(generation_batch)
                generation_batch = split_pixel_values_by_grid(generation_batch)

                try: generation_batch = shuffle_sequence_dict(generation_batch)

                except: pass
                generation_batches = split_tensor_dict(generation_batch, self.args.steps_per_generation)
                self._buffered_inputs = [unsplit_pixel_values_by_grid(batch) for batch in generation_batches]
            inputs = self._buffered_inputs[self._step % self.args.steps_per_generation]
            self._step += 1
        else:
            # In evaluation, there is neither batch grouping for generation, nor multiple iterations, hence
            # local generation batch == local eval batch
            inputs = self._generate_and_score_completions(generation_batch)
        return inputs

    @profiling_decorator
    def _calculate_rewards(self, inputs, prompts, completions, completion_ids_list):
        device = self.accelerator.device
        rewards_per_func = torch.zeros(len(prompts), len(self.reward_funcs), device=device)

        # Repeat all input columns (but "prompt", "completion", and "completion_ids") to match the num of generations
        keys = [key for key in inputs[0] if key not in ["prompt", "completion", "completion_ids"]]
        reward_kwargs = {key: [example[key] for example in inputs] for key in keys}

        # This allows for dynamic reward shaping based on training progress.
        reward_kwargs["trainer_state"] = self.state

        for i, (reward_func, reward_processing_class, reward_func_name) in enumerate(
            zip(self.reward_funcs, self.reward_processing_classes, self.reward_func_names)
        ):
            with profiling_context(self, reward_func_name):
                if isinstance(reward_func, nn.Module):  # Module (no PretrainedModel) for compat with compiled models
                    if is_conversational(inputs[0]):
                        messages = [{"messages": p + c} for p, c in zip(prompts, completions)]
                        texts = [apply_chat_template(x, reward_processing_class)["text"] for x in messages]
                    else:
                        texts = [p + c for p, c in zip(prompts, completions)]
                    reward_inputs = reward_processing_class(
                        text=texts, return_tensors="pt", padding=True, padding_side="right", add_special_tokens=False
                    )
                    reward_inputs = super()._prepare_inputs(reward_inputs)
                    with torch.inference_mode():
                        rewards_per_func[:, i] = reward_func(**reward_inputs).logits[:, 0]  # Shape (B*G,)
                else:
                    output_reward_func = reward_func(
                        prompts=prompts, completions=completions, completion_ids=completion_ids_list, **reward_kwargs
                    )
                    # Convert None values to NaN
                    output_reward_func = [reward if reward is not None else torch.nan for reward in output_reward_func]

                    rewards_per_func[:, i] = torch.tensor(output_reward_func, dtype=torch.float32, device=device)

        # If all reward functions return None for a given row, issue a detailed warning
        if torch.isnan(rewards_per_func).all(dim=1).any():
            nan_row_idx = torch.isnan(rewards_per_func).all(dim=1).nonzero(as_tuple=True)[0][0]
            row_reward_kwargs = {
                key: value[nan_row_idx] for key, value in reward_kwargs.items() if key != "trainer_state"
            }
            row_reward_kwargs["prompt"] = prompts[nan_row_idx]
            row_reward_kwargs["completion"] = completions[nan_row_idx]
            logger.warning(
                f"All reward functions returned None for the following kwargs:\n{row_reward_kwargs}\n"
                "Please ensure that at least one reward function returns a valid reward."
            )

        # Gather the reward per function: this part is crucial, because the rewards are normalized per group and the
        # completions may be distributed across processes
        rewards_per_func = gather(rewards_per_func)
        return rewards_per_func

    def _generate_single_turn(self, prompts: list[str], images: Optional[list]):
        device = self.accelerator.device

        # If the prompts are conversational and the inputs contain images, we need to convert the prompts from
        # [{"role": "user", "content": "What color is the sky?"}] to
        # [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": "What color is the sky?"}]}]
        kwargs = {}
        if images is not None:
            kwargs = {"images": images}
            for prompt, image_list in zip(prompts, images):
                if isinstance(prompt, list):  # i.e., when using conversational data
                    prepare_multimodal_messages(prompt, num_images=len(image_list))

        
        _chat_template_ = getattr(self.processing_class, "chat_template", None)
        if _chat_template_ is None: _chat_template_ = ""
        _supported_keys_ = set(("prompt", "chosen", "rejected", "completion", "messages", "label"))
        _batch_chat_kwargs_ = getattr(self, "_unsloth_batch_chat_kwargs", None)

        prompts_text = []
        for _idx_, _example_ in enumerate(prompts):
            _tokenizer_kwargs_ = {}
            if type(_example_) is not dict:
                _example_ = {"prompt": _example_}
            _left_keys_ = _example_.keys() - _supported_keys_
            for k in _left_keys_:
                if k in _chat_template_:
                    v = _example_[k]
                    if type(v) is str:
                        _tokenizer_kwargs_[k] = v
            if _batch_chat_kwargs_ is not None and _idx_ < len(_batch_chat_kwargs_):
                for _bk_, _bv_ in _batch_chat_kwargs_[_idx_].items():
                    if _bk_ not in _tokenizer_kwargs_:
                        _tokenizer_kwargs_[_bk_] = _bv_
            _x_ = maybe_apply_chat_template(_example_, self.processing_class, **_tokenizer_kwargs_)["prompt"]
            prompts_text.append(_x_)
        if images is not None:
            prompt_inputs = self.processing_class(text=prompts_text, padding=True, return_tensors="pt", **kwargs)
            prompt_inputs = super()._prepare_inputs(prompt_inputs)
            forward_kwargs = {k: v for k, v in prompt_inputs.items() if k not in ["input_ids", "attention_mask"]}
        else:
            forward_kwargs = {}

        # Generate completions using either vLLM or regular generation
        if self.use_vllm:
            if self.vllm_mode == "colocate" and self.args.vllm_enable_sleep_mode:
                # wake up colocated vLLM instances if needed
                torch.cuda.empty_cache()  # required to avoid OOM in some cases
                self.llm.wake_up()

            # First, update the vLLM weights if needed
            if self.state.global_step != self._last_loaded_step:
                self._move_model_to_vllm()
                self._last_loaded_step = self.state.global_step

            # Generate completions using vLLM: gather all prompts and use them in a single call in the main process
            if self.vllm_mode == "server":
                all_prompts_text = gather_object(prompts_text)
                if images is not None:
                    all_images = gather_object(images)

                if self.accelerator.is_main_process:
                    # Since 'prompts' contains 'num_generations' duplicates, we first take unique prompts, and generate
                    # num_generations outputs for each one. This is faster than generating outputs for each duplicate
                    # prompt individually.
                    ordered_set_of_prompts = all_prompts_text[:: self.num_generations]

                    if images is not None:
                        ordered_set_of_images = all_images[:: self.num_generations]
                    else:
                        ordered_set_of_images = None

                    with profiling_context(self, "vLLM.generate"):
                        output = self.vllm_client.generate(
                            prompts=ordered_set_of_prompts,
                            images=ordered_set_of_images,
                            n=self.num_generations,
                            repetition_penalty=self.repetition_penalty,
                            temperature=self.temperature,
                            top_p=self.top_p,
                            top_k=-1 if self.top_k is None else self.top_k,
                            min_p=0.0 if self.min_p is None else self.min_p,
                            max_tokens=self.max_completion_length,
                            truncate_prompt_tokens=self.max_prompt_length,
                            guided_decoding_regex=self.guided_decoding_regex,
                            generation_kwargs=self.args.generation_kwargs,
                        )
                        payload = (output["prompt_ids"], output["completion_ids"], output["logprobs"])
                else:
                    payload = None

                # Broadcast the completions from the main process to all processes, ensuring each process receives its corresponding slice.
                obj_list = [payload]
                broadcast_object_list(obj_list, from_process=0)
                all_prompt_ids, all_completion_ids, all_logprobs = obj_list[0]

                # At this point, we only get 1 copy of each prompt, so we need to repeat them num_generations times
                all_prompt_ids = [ids for ids in all_prompt_ids for _ in range(self.num_generations)]

                process_slice = slice(
                    self.accelerator.process_index * len(prompts),
                    (self.accelerator.process_index + 1) * len(prompts),
                )
                prompt_ids = all_prompt_ids[process_slice]
                completion_ids = all_completion_ids[process_slice]
                logprobs = all_logprobs[process_slice]

            # Generate completions using colocated vLLM instances: each device holds vLLM copy and work on their own batch of prompts
            elif self.vllm_mode == "colocate":
                if self.guided_decoding_regex:
                    guided_decoding = GuidedDecodingParams(regex=self.guided_decoding_regex)
                else:
                    guided_decoding = None

                generation_kwargs = {
                    "n": 1,  # vLLM on each GPU generates only 1 in colocate mode
                    "repetition_penalty": self.repetition_penalty,
                    "temperature": self.temperature,
                    "top_p": self.top_p,
                    "top_k": -1 if self.top_k is None else self.top_k,
                    "min_p": 0.0 if self.min_p is None else self.min_p,
                    "max_tokens": self.max_completion_length,
                    "truncate_prompt_tokens": self.max_prompt_length,
                    "guided_decoding": guided_decoding,
                    "logprobs": 0,  # only return the logprob of the generated token
                }
                if self.args.generation_kwargs is not None:
                    generation_kwargs.update(self.args.generation_kwargs)
                sampling_params = SamplingParams(**grpo_update_SamplingParams(SamplingParams, generation_kwargs, getattr(self.args, 'vllm_sampling_params', None)))

                if self.vllm_tensor_parallel_size > 1:
                    # Gather prompts from all ranks in the TP group and flatten.
                    # Each rank starts with its own prompts; after gathering, all ranks see the full group set.
                    orig_size = len(prompts_text)
                    gathered_prompts = [None for _ in range(self.vllm_tensor_parallel_size)]
                    torch.distributed.all_gather_object(gathered_prompts, prompts_text, group=self.tp_group)
                    all_prompts_text = [p for sublist in gathered_prompts for p in sublist]

                    if images is not None:
                        gathered_images = [None for _ in range(self.vllm_tensor_parallel_size)]
                        torch.distributed.all_gather_object(gathered_images, images, group=self.tp_group)
                        all_images = [img for sublist in gathered_images for img in sublist]
                    else:
                        all_images = None
                else:
                    all_prompts_text = prompts_text
                    all_images = images

                if images is not None and all_images:
                    vllm_inputs = []
                    for prompt, image_list in zip(all_prompts_text, all_images):
                        vllm_inputs.append({"prompt": prompt, "multi_modal_data": {"image": image_list}})

                else:
                    vllm_inputs = all_prompts_text

                with profiling_context(self, "vLLM.generate"):
                    all_outputs = self.llm.generate(vllm_inputs, sampling_params=sampling_params, use_tqdm=False, lora_request = self.model.load_lora('grpo_trainer_lora_model', load_tensors = True) if getattr(self.llm, 'shared_weights', False) else None)

                all_prompt_ids = [output.prompt_token_ids for output in all_outputs]
                all_completion_ids = [output.token_ids for outputs in all_outputs for output in outputs.outputs]
                all_logprobs = [
                    [next(iter(lp.values())).logprob for lp in output.logprobs]
                    for outputs in all_outputs
                    for output in outputs.outputs
                ]

                if self.vllm_tensor_parallel_size > 1:
                    # Slice completions for this rank within its TP group.
                    # Each rank generates all outputs — we keep only our share.
                    local_rank_in_group = torch.distributed.get_rank(group=self.tp_group)
                    tp_slice = slice(local_rank_in_group * orig_size, (local_rank_in_group + 1) * orig_size)
                    prompt_ids = all_prompt_ids[tp_slice]
                    completion_ids = all_completion_ids[tp_slice]
                    logprobs = all_logprobs[tp_slice]
                else:
                    prompt_ids = all_prompt_ids
                    completion_ids = all_completion_ids
                    logprobs = all_logprobs

                if self.args.vllm_enable_sleep_mode:
                    self.llm.sleep(level=1)

        elif self.use_transformers_paged:
            # Re-process inputs for paged generation if needed
            # Note: images are already validated and preprocessed above
            paged_prompt_inputs = self.processing_class(text=prompts_text, **kwargs)
            previous_attn = self.model_wrapped.config._attn_implementation

            if is_flash_attn_2_available():
                self.model_wrapped.config._attn_implementation = "paged_attention"
            else:
                self.model_wrapped.config._attn_implementation = "sdpa_paged"
            with (
                profiling_context(self, "transformers.generate_batch"),
                unwrap_model_for_generation(
                    self.model_wrapped, self.accelerator, gather_deepspeed3_params=self.args.ds3_gather_for_generation
                ) as unwrapped_model,
                torch.no_grad(),
                FSDP.summon_full_params(self.model_wrapped, recurse=False) if self.is_fsdp_enabled else nullcontext(),
            ):
                # Cast to the appropriate dtype based on training configuration
                if self.args.bf16:
                    unwrapped_model.to(torch.bfloat16)
                elif self.args.fp16:
                    unwrapped_model.to(torch.float16)
                with torch.inference_mode():
                    all_outputs = unwrapped_model.generate_batch(
                        paged_prompt_inputs.input_ids, generation_config=self.generation_config, progress_bar=False
                    )
                    unwrapped_model.train()  # restore training mode, as generate_batch forces eval mode
            completion_ids = [output.generated_tokens for output in all_outputs.values()]
            prompt_ids = paged_prompt_inputs.input_ids
            # Restore the original attention implementation, training mode
            self.model_wrapped.config._attn_implementation = previous_attn
            logprobs = None  # not used in this case

        else:
            # Regular generation path
            generate_inputs = self.processing_class(
                text=prompts_text,
                return_tensors="pt",
                padding=True,
                padding_side="left",
                **kwargs,
            )
            generate_inputs = super()._prepare_inputs(generate_inputs)
            if "mm_token_type_ids" in generate_inputs or "image_grid_thw" in generate_inputs:
                mm_token_type_ids = _unsloth_fix_mm_token_type_ids(
                    self.processing_class,
                    generate_inputs["input_ids"],
                    generate_inputs.get("mm_token_type_ids", None),
                )
                if mm_token_type_ids is not None:
                    generate_inputs["mm_token_type_ids"] = mm_token_type_ids

            with (
                profiling_context(self, "transformers.generate"),
                unwrap_model_for_generation(
                    self.model_wrapped, self.accelerator, gather_deepspeed3_params=self.args.ds3_gather_for_generation
                ) as unwrapped_model,
                torch.no_grad(),
                FSDP.summon_full_params(self.model_wrapped, recurse=False) if self.is_fsdp_enabled else nullcontext(),
            ):
                prompt_completion_ids = unwrapped_model.generate(
                    **generate_inputs, generation_config=self.generation_config, disable_compile=True
                )
            # Compute prompt length and extract completion ids
            prompt_ids, prompt_mask = generate_inputs["input_ids"], generate_inputs["attention_mask"]
            prompt_length = prompt_ids.size(1)
            completion_ids = prompt_completion_ids[:, prompt_length:]

            # Mask everything after the first EOS token
            is_eos = completion_ids == self.eos_token_id
            eos_idx = torch.full((is_eos.size(0),), is_eos.size(1), dtype=torch.long, device=device)
            eos_idx[is_eos.any(dim=1)] = is_eos.int().argmax(dim=1)[is_eos.any(dim=1)]
            sequence_indices = torch.arange(is_eos.size(1), device=device).expand(is_eos.size(0), -1)
            completion_mask = (sequence_indices <= eos_idx.unsqueeze(1)).int()
            prompt_ids = [p[m].tolist() for p, m in zip(prompt_ids, prompt_mask.bool())]
            completion_ids = [c[m].tolist() for c, m in zip(completion_ids, completion_mask.bool())]
            logprobs = None  # not used in this case

        return prompt_ids, completion_ids, logprobs, forward_kwargs

    def _generate(self, prompts: list[str], images: Optional[list]):
        device = self.accelerator.device
        mode = "train" if self.model.training else "eval"

        prompt_ids, completion_ids, logprobs, forward_kwargs = self._generate_single_turn(prompts, images)

        # Get completion length per sequence, used for logging
        prompt_lengths = torch.tensor([len(ids) for ids in prompt_ids], device=device)
        completion_lengths = torch.tensor([len(ids) for ids in completion_ids], device=device)
        agg_prompt_lengths = self.accelerator.gather(prompt_lengths)
        agg_completion_lengths = self.accelerator.gather(completion_lengths)
        total_prompt_tokens = agg_prompt_lengths.sum()
        total_completion_tokens = agg_completion_lengths.sum()  # = num_items_in_batch, required for the DAPO loss

        # Log the metrics
        if mode == "train":
            self.state.num_input_tokens_seen += (total_prompt_tokens + total_completion_tokens).item()
        self._metrics[mode]["num_tokens"] = [self.state.num_input_tokens_seen]

        # Log completion lengths, mean, min, max
        self._metrics[mode]["completions/mean_length"].append(agg_completion_lengths.float().mean().item())
        self._metrics[mode]["completions/min_length"].append(agg_completion_lengths.float().min().item())
        self._metrics[mode]["completions/max_length"].append(agg_completion_lengths.float().max().item())

        # Identify sequences that terminated with EOS and log their lengths
        eos_and_pad = [self.eos_token_id, self.pad_token_id]
        is_truncated = torch.tensor([ids[-1] not in eos_and_pad for ids in completion_ids], device=device)
        agg_is_truncated = self.accelerator.gather(is_truncated)
        self._metrics[mode]["completions/clipped_ratio"].append(agg_is_truncated.float().mean().item())
        term_completion_lengths = agg_completion_lengths[~agg_is_truncated]
        if len(term_completion_lengths) == 0:  # edge case where no terminated sequences are found
            term_completion_lengths = torch.zeros(1, device=device)
        self._metrics[mode]["completions/mean_terminated_length"].append(term_completion_lengths.float().mean().item())
        self._metrics[mode]["completions/min_terminated_length"].append(term_completion_lengths.float().min().item())
        self._metrics[mode]["completions/max_terminated_length"].append(term_completion_lengths.float().max().item())

        return prompt_ids, completion_ids, total_completion_tokens, logprobs, forward_kwargs

    def _generate_and_score_completions(
        self, inputs: list[dict[str, Union[torch.Tensor, Any]]]
    ) -> dict[str, Union[torch.Tensor, Any]]:
        device = self.accelerator.device
        mode = "train" if self.model.training else "eval"

        prompts = [x["prompt"] for x in inputs]
        # Unsloth: Extract per-sample chat_template_kwargs before metadata is lost
        _ct_ = getattr(self.processing_class, 'chat_template', None) or ''
        _sk_ = {'prompt', 'chosen', 'rejected', 'completion', 'messages', 'label',
                'images', 'image', 'videos', 'video', 'audios', 'audio'}
        self._unsloth_batch_chat_kwargs = []
        for _inp_ in inputs:
            _kw_ = {}
            if isinstance(_inp_, dict):
                for _k_ in _inp_.keys() - _sk_:
                    if _k_ in _ct_ and isinstance(_inp_[_k_], str):
                        _kw_[_k_] = _inp_[_k_]
            self._unsloth_batch_chat_kwargs.append(_kw_)
        if "images" in inputs[0]:
            images = [example.get("images") for example in inputs]
        elif "image" in inputs[0]:
            images = [[example.get("image")] if example.get("image") is not None else None for example in inputs]
        else:
            images = None
        # Transformers requires at least one image in the batch, otherwise it throws an error
        if images is not None and all(img_list == [] for img_list in images):
            images = None

        (
            prompt_ids_list,
            completion_ids_list,
            num_items_in_batch,
            sampling_per_token_logps_list,
            forward_kwargs,
        ) = self._generate(prompts, images)

        # Convert lists of token IDs to padded tensors
        prompt_ids = [torch.tensor(ids, device=device) for ids in prompt_ids_list]
        prompt_mask = [torch.ones_like(ids, dtype=torch.long) for ids in prompt_ids]
        prompt_ids = pad(prompt_ids, padding_value=self.pad_token_id, padding_side="left")
        prompt_mask = pad(prompt_mask, padding_value=0, padding_side="left")
        completion_ids = [torch.tensor(ids, device=device) for ids in completion_ids_list]
        completion_mask = [torch.ones_like(ids, dtype=torch.long) for ids in completion_ids]
        completion_ids = pad(completion_ids, padding_value=self.pad_token_id, padding_side="right")
        completion_mask = pad(completion_mask, padding_value=0, padding_side="right")
        if sampling_per_token_logps_list is not None:
            sampling_per_token_logps = [torch.tensor(logps, device=device) for logps in sampling_per_token_logps_list]
            sampling_per_token_logps = pad(sampling_per_token_logps, padding_value=0.0, padding_side="right")
        else:
            sampling_per_token_logps = None

        # If mask_truncated_completions is enabled, zero out truncated completions in completion_mask
        if self.mask_truncated_completions:
            eos_and_pad = [self.eos_token_id, self.pad_token_id]
            is_truncated = torch.tensor([ids[-1] not in eos_and_pad for ids in completion_ids_list], device=device)
            completion_mask = completion_mask * (~is_truncated).unsqueeze(1).int()

        # Concatenate prompt_mask with completion_mask for logit computation
        prompt_completion_ids = torch.cat([prompt_ids, completion_ids], dim=1)  # (B, P+C)
        attention_mask = torch.cat([prompt_mask, completion_mask], dim=1)  # (B, P+C)
        # If token_type_ids are used, extend them with zeros for the completion part
        if "token_type_ids" in forward_kwargs:
            token_type_ids = forward_kwargs["token_type_ids"]
            forward_kwargs["token_type_ids"] = torch.cat(
                [token_type_ids, token_type_ids.new_zeros(completion_ids.shape)], dim=1
            )

        if "mm_token_type_ids" in forward_kwargs or "image_grid_thw" in forward_kwargs:
            _mm_token_type_ids = _unsloth_fix_mm_token_type_ids(
                self.processing_class,
                prompt_completion_ids,
                forward_kwargs.get("mm_token_type_ids", None),
                completion_ids = completion_ids,
            )
            if _mm_token_type_ids is not None:
                forward_kwargs["mm_token_type_ids"] = _mm_token_type_ids

        logits_to_keep = completion_ids.size(1)  # we only need to compute the logits for the completion tokens
        
        max_left_pad = None
        batch_size = self.args.per_device_train_batch_size if mode == "train" else self.args.per_device_eval_batch_size
        try:
            # TRL 0.23.1 and below path
            if not has_images:
                # Left pad prompt before calculation old and ref hidden states
                left_pad_tokens_per_prompt = calculate_pad_tokens_in_prompt(prompt_completion_ids, logits_to_keep, self.processing_class.pad_token_id)
                max_left_pad = torch.max(left_pad_tokens_per_prompt).item()
        except:
            # TRL 0.24.0 and below path
            if images is None:
                # Left pad prompt before calculation old and ref hidden states
                left_pad_tokens_per_prompt = calculate_pad_tokens_in_prompt(prompt_completion_ids, logits_to_keep, self.processing_class.pad_token_id)
                max_left_pad = torch.max(left_pad_tokens_per_prompt).item()
        _use_gc = self.model._unsloth_gradient_checkpointing if hasattr(self.model, '_unsloth_gradient_checkpointing') else getattr(self.args, 'gradient_checkpointing', True)
        self.model.for_training(use_gradient_checkpointing=_use_gc)

        num_images = [len(img_list) for img_list in images] if images is not None else None

        with torch.no_grad():
            # If the generation and optimization steps are misaligned—i.e., if generation does not occur at the end of
            # a full optimizer step (when gradient_accumulation_steps is not a multiple of generate_every)—then the
            # samples may come from an earlier version of the model. In that case, we need to track old_per_token_logps
            # for importance sampling. If the steps are aligned, importance sampling isn't necessary and we set
            # old_per_token_logps to None.
            # When using vLLM, we always compute old_per_token_logps for importance sampling, it was shown that the
            # distribution mismatch between vLLM and the training model can be large and harm the training.
            generate_every = self.args.steps_per_generation * self.num_iterations  # generation frequency

            if self.args.gradient_accumulation_steps % generate_every != 0 or (
                self.use_vllm
            ):
                old_per_token_logps, _ = self._get_per_token_logps_and_entropies(
                    self.model,
                    prompt_completion_ids,
                    attention_mask,
                    logits_to_keep,
                    batch_size,
                    num_images=num_images,
                    **forward_kwargs,  # may contain pixel_values, image_grid_thw, pixel_attention_mask and image_sizes
                )
            else:
                old_per_token_logps = None

            # Compute the importance sampling ratio when using vLLM, to correct for potential distribution mismatch
            if False and self.use_vllm and self.vllm_importance_sampling_correction:
                importance_sampling_ratio = torch.exp(old_per_token_logps - sampling_per_token_logps)
                importance_sampling_ratio = torch.clamp(
                    importance_sampling_ratio, max=self.vllm_importance_sampling_cap
                )

            # Compute the per-token log probabilities for the reference model
            if self.beta != 0.0:
                if self.ref_model is not None:
                    ref_per_token_logps, _ = self._get_per_token_logps_and_entropies(
                        self.ref_model,
                        prompt_completion_ids,
                        attention_mask,
                        logits_to_keep,
                        batch_size=batch_size,
                        num_images=num_images,
                        **forward_kwargs,  # may contain pixel_values, image_grid_thw, pixel_attention_mask and image_sizes
                    )
                else:
                    with self.accelerator.unwrap_model(self.model).disable_adapter():
                        ref_per_token_logps, _ = self._get_per_token_logps_and_entropies(
                            self.model,
                            prompt_completion_ids,
                            attention_mask,
                            logits_to_keep,
                            batch_size=batch_size,
                            num_images=num_images,
                            **forward_kwargs,  # may contain pixel_values, image_grid_thw, pixel_attention_mask and image_sizes
                        )
            else:
                ref_per_token_logps = None

        # Decode
        prompts_text = self.processing_class.batch_decode(prompt_ids, skip_special_tokens=True)
        completions_text = self.processing_class.batch_decode(completion_ids, skip_special_tokens=True)
        if is_conversational(inputs[0]):
            completions = []
            for prompt, completion in zip(prompts, completions_text):
                bootstrap = prompt.pop()["content"] if prompt[-1]["role"] == "assistant" else ""
                completions.append([{"role": "assistant", "content": bootstrap + completion}])
        else:
            completions = completions_text

        # Calculate rewards for each reward function. rewards_per_func aggregates rewards across all processes. This is
        # important because rewards will be normalized per group, and completions are distributed. We will later slice
        # rewards_per_func to extract each process's subset.
        if images is not None:
            rewards_per_func = self._calculate_rewards(inputs, prompts_text, completions_text, completion_ids_list)
        else:
            rewards_per_func = self._calculate_rewards(inputs, prompts, completions, completion_ids_list)

        # Apply weights to each reward function's output and sum
        rewards = (rewards_per_func * self.reward_weights.to(device).unsqueeze(0)).nansum(dim=1)

        # Compute grouped-wise rewards
        mean_grouped_rewards = rewards.view(-1, self.num_generations).mean(dim=1)

        # Normalize the rewards to compute the advantages
        mean_grouped_rewards = mean_grouped_rewards.repeat_interleave(self.num_generations, dim=0)
        advantages = rewards - mean_grouped_rewards

        if self.scale_rewards in ["group", "none"]:
            # If self.scale_rewards = "none", we'll still log group level std
            std_rewards = rewards.view(-1, self.num_generations).std(dim=1)
            std_rewards = std_rewards.repeat_interleave(self.num_generations, dim=0)
        elif self.scale_rewards == "batch":
            # Compute global std
            std_rewards = rewards.std().expand_as(rewards)
        else:
            raise ValueError(
                f"Invalid value for scale_rewards: {self.scale_rewards}. Must be one of 'batch', 'group', or 'none'."
            )

        is_std_zero = torch.isclose(std_rewards, torch.zeros_like(std_rewards))
        if self.scale_rewards != "none":
            advantages = advantages / (std_rewards + 1e-4)

        # Slice to keep only the local part of the data
        process_slice = slice(
            self.accelerator.process_index * len(prompts),
            (self.accelerator.process_index + 1) * len(prompts),
        )
        all_process_advantages = advantages.clone()  # keep the aggregated advantages for logging
        advantages = advantages[process_slice]

        # Calculate mean reward per function, but only for samples where the function was applied (non-NaN values)
        for i, reward_func_name in enumerate(self.reward_func_names):
            mean_rewards = torch.nanmean(rewards_per_func[:, i]).item()
            self._metrics[mode][f"rewards/{reward_func_name}/mean"].append(mean_rewards)
            std_func_rewards = nanstd(rewards_per_func[:, i]).item()
            self._metrics[mode][f"rewards/{reward_func_name}/std"].append(std_func_rewards)
        self._metrics[mode]["reward"].append(mean_grouped_rewards.mean().item())
        self._metrics[mode]["reward_std"].append(std_rewards.mean().item())
        self._metrics[mode]["frac_reward_zero_std"].append(is_std_zero.float().mean().item())

        # Log prompt and completion texts
        self._logs["prompt"].extend(gather_object(prompts_text))
        self._logs["completion"].extend(gather_object(completions_text))
        for i, name in enumerate(self.reward_func_names):
            self._logs["rewards"][name].extend(rewards_per_func[:, i].tolist())
        self._logs["advantages"].extend(all_process_advantages.tolist())

        if images is not None:
            self._logs["images"].extend(gather_object(images))

        if False and self.use_vllm and self.vllm_importance_sampling_correction:
            delta = torch.abs(old_per_token_logps - sampling_per_token_logps)
            delta = delta[completion_mask.bool()]
            mean_delta = torch.mean(delta) if delta.numel() > 0 else torch.tensor(0.0, device=device)
            max_delta = torch.max(delta) if delta.numel() > 0 else torch.tensor(0.0, device=device)
            self._metrics[mode]["sampling/sampling_logp_difference/mean"].append(
                self.accelerator.gather(mean_delta).mean().item()
            )
            self._metrics[mode]["sampling/sampling_logp_difference/max"].append(
                self.accelerator.gather(max_delta).max().item()
            )

            flat_is_ratio = importance_sampling_ratio[completion_mask.bool()]
            min_importance_sampling_ratio = (
                torch.min(flat_is_ratio) if flat_is_ratio.numel() > 0 else torch.tensor(0.0, device=device)
            )
            mean_importance_sampling_ratio = (
                torch.mean(flat_is_ratio) if flat_is_ratio.numel() > 0 else torch.tensor(0.0, device=device)
            )
            max_importance_sampling_ratio = (
                torch.max(flat_is_ratio) if flat_is_ratio.numel() > 0 else torch.tensor(0.0, device=device)
            )
            self._metrics[mode]["sampling/importance_sampling_ratio/min"].append(
                nanmin(self.accelerator.gather(min_importance_sampling_ratio)).item()
            )
            self._metrics[mode]["sampling/importance_sampling_ratio/mean"].append(
                self.accelerator.gather(mean_importance_sampling_ratio).nanmean().item()
            )
            self._metrics[mode]["sampling/importance_sampling_ratio/max"].append(
                nanmax(self.accelerator.gather(max_importance_sampling_ratio)).item()
            )

        output = {
            "prompt_ids": prompt_ids,
            "prompt_mask": prompt_mask,
            "completion_ids": completion_ids,
            "completion_mask": completion_mask,
            "advantages": advantages,
            "num_items_in_batch": num_items_in_batch,
        }
        if old_per_token_logps is not None:
            output["old_per_token_logps"] = old_per_token_logps
        if False and self.use_vllm and self.vllm_importance_sampling_correction:
            output["importance_sampling_ratio"] = importance_sampling_ratio
        if ref_per_token_logps is not None:
            output["ref_per_token_logps"] = ref_per_token_logps
        if "pixel_values" in forward_kwargs:
            output["pixel_values"] = forward_kwargs["pixel_values"]
        if "image_grid_thw" in forward_kwargs:
            output["image_grid_thw"] = forward_kwargs["image_grid_thw"]
        if "pixel_attention_mask" in forward_kwargs:
            output["pixel_attention_mask"] = forward_kwargs["pixel_attention_mask"]
        if "image_sizes" in forward_kwargs:
            output["image_sizes"] = forward_kwargs["image_sizes"]
        if "token_type_ids" in forward_kwargs:
            output["token_type_ids"] = forward_kwargs["token_type_ids"]
        if "mm_token_type_ids" in forward_kwargs:
            output["mm_token_type_ids"] = forward_kwargs["mm_token_type_ids"]
        if images is not None:
            output["num_images"] = num_images
        if max_left_pad is not None:
            output["max_left_pad"] = torch.tensor(prompt_ids.shape[0] * [max_left_pad]).unsqueeze(-1)
        try:
            if self.use_vllm and getattr(self, "vllm_importance_sampling_correction", False):
                output["sampling_per_token_logps"] = sampling_per_token_logps
        except NameError:
            output["sampling_per_token_logps"] = None
        return output

    def compute_liger_loss(self, unwrapped_model, inputs):
        # Compute the per-token log probabilities for the model
        prompt_ids, prompt_mask = inputs["prompt_ids"], inputs["prompt_mask"]
        completion_ids, completion_mask = inputs["completion_ids"], inputs["completion_mask"]
        input_ids = torch.cat([prompt_ids, completion_ids], dim=1)
        attention_mask = torch.cat([prompt_mask, completion_mask], dim=1)
        logits_to_keep = completion_ids.size(1)  # we only need to compute the logits for the completion tokens

        # Get the last hidden state of the model
        last_hidden_state = self._get_last_hidden_state(
            unwrapped_model,
            input_ids,
            attention_mask,
            logits_to_keep,
            inputs.get("pixel_values"),
            inputs.get("image_grid_thw"),
            inputs.get("pixel_attention_mask"),
            inputs.get("image_sizes"),
        )

        # compute loss and metrics using liger grpo loss
        loss, metrics = self.liger_grpo_loss(
            _input=last_hidden_state,
            lin_weight=unwrapped_model.lm_head.weight,
            selected_token_ids=completion_ids,
            attention_mask=completion_mask,
            advantages=inputs["advantages"],
            bias=unwrapped_model.lm_head.bias,
            old_per_token_logps=inputs.get("old_per_token_logps"),
            ref_per_token_logps=inputs.get("ref_per_token_logps"),
        )
        # Extract metrics from the liger_grpo_loss output
        # KL divergence is the first metric when beta is non-zero
        mean_kl = metrics[0] if self.beta != 0.0 else None
        clip_ratio = metrics[-1]

        mode = "train" if self.model.training else "eval"
        if self.beta != 0.0:
            self._metrics[mode]["kl"].append(self.accelerator.gather(mean_kl).mean().item())
        self._metrics[mode]["clip_ratio"].append(self.accelerator.gather(clip_ratio).mean().item())
        return loss / self.current_gradient_accumulation_steps

    def compute_loss(
        self,
        model,
        inputs,
        return_outputs = False,
        num_items_in_batch = None,
    ):
        if return_outputs:
            raise ValueError("The GRPOTrainer does not support returning outputs")
        # Compute the per-token log probabilities for the model

        prompt_ids, prompt_mask = inputs["prompt_ids"], inputs["prompt_mask"]
        completion_ids, completion_mask = (
            inputs["completion_ids"],
            inputs["completion_mask"],
        )
        pixel_values, image_grid_thw = (
            inputs.get("pixel_values", None),
            inputs.get("image_grid_thw", None),
        )
        pixel_attention_mask, image_sizes = (
            inputs.get("pixel_attention_mask", None),
            inputs.get("image_sizes", None),
        )
        num_images = inputs.get("num_images", None)
        # Transformers 5.x needs token_type_ids/mm_token_type_ids for some vision models
        token_type_ids = inputs.get("token_type_ids", None)
        mm_token_type_ids = inputs.get("mm_token_type_ids", None)
        num_items_in_batch = inputs.get("num_items_in_batch", None)
        sampling_per_token_logps = inputs.get("sampling_per_token_logps", None)
        tool_mask = inputs.get("tool_mask", None)
        # Missing when evaluate() runs standalone; eval does not accumulate, so
        # fall back to 1 to avoid underreporting eval_loss (#2464).
        current_gradient_accumulation_steps = getattr(
            self, "current_gradient_accumulation_steps", 1
        )
        num_processes = self.accelerator.num_processes

        input_ids = torch.cat([prompt_ids, completion_ids], dim = 1)
        bsz, qlen = input_ids.shape
        attention_mask = torch.cat([prompt_mask, completion_mask], dim = 1)
        if mm_token_type_ids is not None or image_grid_thw is not None:
            mm_token_type_ids = _unsloth_fix_mm_token_type_ids(
                self.processing_class,
                input_ids,
                mm_token_type_ids,
                completion_ids = completion_ids,
            )
        # attention_mask = None
        logits_to_keep = completion_ids.size(
            1
        )  # we only need to compute the logits for the completion tokens
        _input_ids = input_ids
        _logits_to_keep = logits_to_keep

        get_logps_func = (
            lambda model,
            input_ids,
            attention_mask,
            logits_to_keep,
            batch_size = None,
            compute_entropy = False,
            compute_efficient = False: (
                self._get_per_token_logps(
                    model, input_ids, attention_mask, logits_to_keep, compute_efficient
                )
                if hasattr(self, "_get_per_token_logps")
                else self._get_per_token_logps_and_entropies(
                    model,
                    input_ids,
                    attention_mask,
                    logits_to_keep,
                    batch_size,
                    compute_entropy,
                    compute_efficient,
                )[0]
            )
        )  # logps

        per_token_logps = get_logps_func(
            model, input_ids, attention_mask, logits_to_keep, compute_efficient = True
        )
        # Compute the KL divergence between the model and the reference model
        # _prepare_inputs doesn't return reference log probs anymore. We need to calculate it ourselves.
        # https://github.com/huggingface/trl/blob/05bc43e960396581e458195b8388efe6b82cae1f/trl/trainer/grpo_trainer.py#L1328
        # if self.beta != 0.0:
        #     with torch.inference_mode(), model.disable_adapter():
        #         ref_per_token_logps = per_token_logps = get_logps_func(model, input_ids, attention_mask, logits_to_keep)
        # else:
        #     ref_per_token_logps = None
        ref_logps = inputs.get("ref_per_token_logps", None)
        # per_token_kl = torch.exp(ref_per_token_logps - per_token_logps) - (ref_per_token_logps - per_token_logps) - 1
        # x - x.detach() allows for preserving gradients from x
        advantages = inputs["advantages"]
        # per_token_loss = torch.exp(per_token_logps - per_token_logps.detach()) * advantages.unsqueeze(1)
        # per_token_loss = -(per_token_loss - self.beta * per_token_kl)
        # loss = ((per_token_loss * completion_mask).sum(dim=1) / completion_mask.sum(dim=1)).mean()
        old_logps = inputs.get("old_per_token_logps", None)

        input_ids = input_ids[:, -logits_to_keep:]

        # Get logit softcapping and logit scale
        model_config = _unsloth_get_model_config(model)
        logit_softcapping = _unsloth_get_final_logit_softcapping(model)  # Gemma
        logit_scale_multiply = getattr(model_config, "logit_scale", 0)  # Cohere
        if logit_scale_multiply is None:
            logit_scale_multiply = 0
        logit_scale_divide = getattr(model_config, "logits_scaling", 0)  # Granite
        if logit_scale_divide is None:
            logit_scale_divide = 0

        max_left_pad = inputs.get("max_left_pad", 0)
        if per_token_logps is not None:
            loss_mask = completion_mask
            if tool_mask is not None:
                if tool_mask.shape != completion_mask.shape:
                    raise ValueError(
                        "tool_mask/env_mask must have the same shape as completion_mask"
                    )
                loss_mask = completion_mask * tool_mask.to(
                    device = completion_mask.device,
                    dtype = completion_mask.dtype,
                )
            (
                loss,
                completion_length,
                mean_kl,
                delta,
                flat_is_ratio,
                coef_1,
                completion_mask,
            ) = grpo_compute_loss_slow(
                ref_logps,
                per_token_logps,
                old_logps,
                sampling_per_token_logps,
                input_ids,
                loss_mask,
                self.beta,
                advantages,
                pixel_values = pixel_values,
                image_grid_thw = image_grid_thw,
                loss_type = self.args.loss_type,
                importance_sampling_level = self.importance_sampling_level,
                epsilon_low = self.epsilon_low,
                epsilon_high = self.epsilon_high,
                max_completion_length = self.args.max_completion_length,
                delta = self.args.delta,
                temperature = self.args.temperature,
                max_left_pad = max_left_pad,
                logit_softcapping = logit_softcapping,
                logit_scale_multiply = logit_scale_multiply,
                logit_scale_divide = logit_scale_divide,
                num_items_in_batch = num_items_in_batch,
                current_gradient_accumulation_steps = current_gradient_accumulation_steps,
                num_processes = num_processes,
            )
        else:

            def _unsloth_requires_multi_image_zoo(value):
                if value is None:
                    return False
                if isinstance(value, torch.Tensor):
                    counts = value.detach().cpu().reshape(-1).tolist()
                else:
                    counts = list(value)
                return any(int(n) != 1 for n in counts)

            if _unsloth_requires_multi_image_zoo(num_images) and not getattr(
                self, "_unsloth_grpo_zoo_checked", False
            ):
                _supports_num_images = (
                    "num_images" in inspect.signature(grpo_accumulated_loss).parameters
                )
                if not _supports_num_images:
                    try:
                        _zoo_src = inspect.getsource(grpo_accumulated_loss)
                    except (TypeError, OSError):
                        _zoo_src = ""
                    _supports_num_images = "num_images" in _zoo_src
                if not _supports_num_images:
                    raise RuntimeError(
                        "Multi-image GRPO requires an unsloth_zoo build whose "
                        "grpo_accumulated_loss handles num_images. Please upgrade "
                        "unsloth_zoo (see https://github.com/unslothai/unsloth-zoo/pull/613)."
                    )
                self._unsloth_grpo_zoo_checked = True
            if tool_mask is not None and not getattr(
                self, "_unsloth_grpo_tool_mask_zoo_checked", False
            ):
                _supports_tool_mask = (
                    "tool_mask" in inspect.signature(grpo_accumulated_loss).parameters
                )
                if not _supports_tool_mask:
                    try:
                        _zoo_src = inspect.getsource(grpo_accumulated_loss)
                    except (TypeError, OSError):
                        _zoo_src = ""
                    _supports_tool_mask = "tool_mask" in _zoo_src
                if not _supports_tool_mask:
                    raise RuntimeError(
                        "env_mask/tool_mask GRPO requires an unsloth_zoo build whose "
                        "grpo_accumulated_loss handles tool_mask. Please upgrade "
                        "unsloth_zoo."
                    )
                self._unsloth_grpo_tool_mask_zoo_checked = True
            _grpo_accumulated_loss_kwargs = {}
            if tool_mask is not None:
                _grpo_accumulated_loss_kwargs["tool_mask"] = tool_mask
            if hasattr(self.args, "loss_type"):
                (
                    loss,
                    completion_length,
                    mean_kl,
                    delta,
                    flat_is_ratio,
                    coef_1,
                    completion_mask,
                ) = grpo_accumulated_loss(
                    trainer = self,
                    input_ids = _input_ids,
                    pixel_values = pixel_values,
                    image_grid_thw = image_grid_thw,
                    pixel_attention_mask = pixel_attention_mask,
                    image_sizes = image_sizes,
                    num_images = num_images,
                    logits_to_keep = logits_to_keep,
                    completion_mask = completion_mask,
                    advantages = advantages,
                    old_logps = old_logps,
                    ref_logps = ref_logps,
                    n_chunks = self.args.unsloth_num_chunks,
                    loss_type = self.args.loss_type,
                    importance_sampling_level = self.importance_sampling_level,
                    epsilon_low = self.epsilon_low,
                    epsilon_high = self.epsilon_high,
                    max_completion_length = self.args.max_completion_length,
                    delta = self.args.delta,
                    temperature = self.args.temperature,
                    max_left_pad = max_left_pad,
                    logit_softcapping = logit_softcapping,
                    logit_scale_multiply = logit_scale_multiply,
                    logit_scale_divide = logit_scale_divide,
                    attention_mask = attention_mask,
                    num_items_in_batch = num_items_in_batch,
                    current_gradient_accumulation_steps = current_gradient_accumulation_steps,
                    num_processes = num_processes,
                    sampling_per_token_logps = sampling_per_token_logps,
                    token_type_ids = token_type_ids,
                    mm_token_type_ids = mm_token_type_ids,
                    **_grpo_accumulated_loss_kwargs,
                )
            else:
                # to ensure backwards compatibility with trl 0.15.2 and maybe even 0.17
                loss, completion_length, mean_kl, coef_1, completion_mask = grpo_accumulated_loss(
                    trainer = self,
                    input_ids = _input_ids,
                    pixel_values = pixel_values,
                    image_grid_thw = image_grid_thw,
                    pixel_attention_mask = pixel_attention_mask,
                    image_sizes = image_sizes,
                    num_images = num_images,
                    logits_to_keep = logits_to_keep,
                    completion_mask = completion_mask,
                    advantages = advantages,
                    old_logps = old_logps,
                    ref_logps = ref_logps,
                    n_chunks = self.args.unsloth_num_chunks,
                    temperature = self.args.temperature,
                    logit_softcapping = logit_softcapping,
                    logit_scale_multiply = logit_scale_multiply,
                    logit_scale_divide = logit_scale_divide,
                    attention_mask = attention_mask,
                    token_type_ids = token_type_ids,
                    mm_token_type_ids = mm_token_type_ids,
                    **_grpo_accumulated_loss_kwargs,
                )
        if "train" in self._metrics:
            mode = "eval" if self.control.should_evaluate else "train"
            self._metrics[mode]["completion_length"].append(completion_length.item())
            self._metrics[mode]["kl"].append(mean_kl.item())
        else:
            self._metrics["completion_length"].append(completion_length.item())
            self._metrics["kl"].append(mean_kl.item())

        if (
            self.use_vllm
            and delta is not None
            and getattr(self, "vllm_importance_sampling_correction", False)
        ):
            mean_delta = (
                torch.mean(delta)
                if delta.numel() > 0
                else torch.tensor(0.0, device = self.model.device)
            )
            max_delta = (
                torch.max(delta)
                if delta.numel() > 0
                else torch.tensor(0.0, device = self.model.device)
            )
            self._metrics[mode]["sampling/sampling_logp_difference/mean"].append(
                self.accelerator.gather(mean_delta).mean().item()
            )
            self._metrics[mode]["sampling/sampling_logp_difference/max"].append(
                self.accelerator.gather(max_delta).max().item()
            )

            min_importance_sampling_ratio = (
                torch.min(flat_is_ratio)
                if flat_is_ratio.numel() > 0
                else torch.tensor(0.0, device = self.model.device)
            )
            mean_importance_sampling_ratio = (
                torch.mean(flat_is_ratio)
                if flat_is_ratio.numel() > 0
                else torch.tensor(0.0, device = self.model.device)
            )
            max_importance_sampling_ratio = (
                torch.max(flat_is_ratio)
                if flat_is_ratio.numel() > 0
                else torch.tensor(0.0, device = self.model.device)
            )
            self._metrics[mode]["sampling/importance_sampling_ratio/min"].append(
                self.accelerator.gather(min_importance_sampling_ratio)
                .nan_to_num(nan = float("inf"))
                .min()
                .item()
            )
            self._metrics[mode]["sampling/importance_sampling_ratio/mean"].append(
                self.accelerator.gather(mean_importance_sampling_ratio).nanmean().item()
            )
            self._metrics[mode]["sampling/importance_sampling_ratio/max"].append(
                self.accelerator.gather(max_importance_sampling_ratio)
                .nan_to_num(nan = float("-inf"))
                .max()
                .item()
            )

        completion_token_count = completion_mask.sum().clamp(min = 1.0)

        def masked_batch_mean(x):
            if x.shape[1] == 1:  # when importance_sampling_level == "sequence"
                return x.mean()
            else:
                return (x * completion_mask).sum() / completion_token_count

        if advantages.dim() == 1:
            advantages = advantages.unsqueeze(1)

        if self.loss_type in ["grpo", "bnpo", "dr_grpo", "dapo"]:
            # Compute the clipped probability ratios
            is_low_clipped = (coef_1 < 1 - self.epsilon_low) & (advantages < 0)
            is_high_clipped = (coef_1 > 1 + self.epsilon_high) & (advantages > 0)
            is_region_clipped = is_low_clipped | is_high_clipped

            low_clip = masked_batch_mean(is_low_clipped.float())
            high_clip = masked_batch_mean(is_high_clipped.float())
            clip_ratio = masked_batch_mean(is_region_clipped.float())

            gathered_low_clip = self.accelerator.gather(low_clip)
            self._metrics[mode]["clip_ratio/low_mean"].append(gathered_low_clip.nanmean().item())
            self._metrics[mode]["clip_ratio/low_min"].append(nanmin(gathered_low_clip).item())
            gathered_high_clip = self.accelerator.gather(high_clip)
            self._metrics[mode]["clip_ratio/high_mean"].append(gathered_high_clip.nanmean().item())
            self._metrics[mode]["clip_ratio/high_max"].append(nanmax(gathered_high_clip).item())
            gathered_clip_ratio = self.accelerator.gather(clip_ratio)
            self._metrics[mode]["clip_ratio/region_mean"].append(
                gathered_clip_ratio.nanmean().item()
            )
        elif self.loss_type == "cispo":
            is_cispo_clipped = (coef_1 > self.epsilon_high) & (advantages > 0)
            cispo_clip_ratio = masked_batch_mean(is_cispo_clipped.float())
            gathered_cispo_clip_ratio = self.accelerator.gather(cispo_clip_ratio)
            self._metrics[mode]["cispo_clip_ratio"].append(
                gathered_cispo_clip_ratio.nanmean().item()
            )

        return loss

    def _compute_loss(self, model, inputs):
        # Compute the per-token log probabilities for the model
        prompt_ids, prompt_mask = inputs["prompt_ids"], inputs["prompt_mask"]
        completion_ids, completion_mask = inputs["completion_ids"], inputs["completion_mask"]
        input_ids = torch.cat([prompt_ids, completion_ids], dim=1)
        attention_mask = torch.cat([prompt_mask, completion_mask], dim=1)
        logits_to_keep = completion_ids.size(1)  # we only need to compute the logits for the completion tokens

        # Compute the per_token_logps and the entropy at each position in the completion
        per_token_logps, entropies = self._get_per_token_logps_and_entropies(
            model,
            input_ids,
            attention_mask,
            logits_to_keep,
            compute_entropy=True,
            pixel_values=inputs.get("pixel_values"),
            image_grid_thw=inputs.get("image_grid_thw"),
            num_images=inputs.get("num_images"),
            pixel_attention_mask=inputs.get("pixel_attention_mask"),
            image_sizes=inputs.get("image_sizes"),
            token_type_ids=inputs.get("token_type_ids"),
        )

        if self.top_entropy_quantile < 1.0:
            entropy_mask = self.get_high_entropy_mask(entropies, completion_mask, 1 - self.top_entropy_quantile)
        else:
            entropy_mask = None

        # Compute the KL divergence between the model and the reference model
        if self.beta != 0.0:
            ref_per_token_logps = inputs["ref_per_token_logps"]
            per_token_kl = (
                torch.exp(ref_per_token_logps - per_token_logps) - (ref_per_token_logps - per_token_logps) - 1
            )

        # Compute the loss
        advantages = inputs["advantages"]
        # When num_iterations == 1 and steps_per_generation <= gradient_accumulation_steps,
        # old_per_token_logps == per_token_logps. In this case we can skip its computation
        # (see _generate_and_score_completions) and instead use per_token_logps.detach().
        # The exception is when using vLLM, where we always compute old_per_token_logps
        # for importance sampling
        old_per_token_logps = inputs.get("old_per_token_logps")
        old_per_token_logps = per_token_logps.detach() if old_per_token_logps is None else old_per_token_logps

        log_ratio = per_token_logps - old_per_token_logps
        if self.importance_sampling_level == "token":
            log_importance_weights = log_ratio
        elif self.importance_sampling_level == "sequence":
            log_importance_weights = (log_ratio * completion_mask).sum(-1) / completion_mask.sum(-1).clamp(min=1.0)
            log_importance_weights = log_importance_weights.unsqueeze(-1)
        else:
            raise ValueError(
                f"Unknown importance sampling level: {self.importance_sampling_level}. Possible values are 'token' "
                "and 'sequence'."
            )
        # From here, log_importance_weights (and all subsequent tensors, coef_1, coef_2, etc.) shape depends on
        # importance_sampling_level: "token" level: (B, T); "sequence" level: (B, 1)

        coef_1 = torch.exp(log_importance_weights)
        coef_2 = torch.clamp(coef_1, 1 - self.epsilon_low, 1 + self.epsilon_high)

        # Two-sided clipping
        if self.args.delta is not None:
            coef_1 = torch.clamp(coef_1, max=self.args.delta)

        per_token_loss1 = coef_1 * advantages.unsqueeze(1)
        per_token_loss2 = coef_2 * advantages.unsqueeze(1)
        per_token_loss = -torch.min(per_token_loss1, per_token_loss2)
        if entropy_mask is not None:
            per_token_loss = per_token_loss * entropy_mask

        if self.use_vllm and self.vllm_importance_sampling_correction:
            per_token_loss = per_token_loss * inputs["importance_sampling_ratio"]

        if self.beta != 0.0:
            per_token_loss = per_token_loss + self.beta * per_token_kl

        if self.loss_type == "grpo":
            loss = ((per_token_loss * completion_mask).sum(-1) / completion_mask.sum(-1).clamp(min=1.0)).mean()
            loss = loss / self.current_gradient_accumulation_steps
        elif self.loss_type == "bnpo":
            loss = (per_token_loss * completion_mask).sum() / completion_mask.sum().clamp(min=1.0)
            loss = loss / self.current_gradient_accumulation_steps
        elif self.loss_type == "dr_grpo":
            loss = (per_token_loss * completion_mask).sum() / (per_token_loss.size(0) * self.max_completion_length)
            loss = loss / self.current_gradient_accumulation_steps
        elif self.loss_type == "dapo":
            normalizer = inputs["num_items_in_batch"] / self.accelerator.num_processes
            loss = (per_token_loss * completion_mask).sum() / normalizer
        else:
            raise ValueError(f"Unknown loss type: {self.loss_type}")

        # Log the metrics
        mode = "train" if self.model.training else "eval"

        completion_token_count = completion_mask.sum().clamp(min=1.0)

        def masked_batch_mean(x):
            if x.shape[1] == 1:  # when importance_sampling_level == "sequence"
                return x.mean()
            else:
                return (x * completion_mask).sum() / completion_token_count

        if self.beta != 0.0:
            mean_kl = masked_batch_mean(per_token_kl)
            self._metrics[mode]["kl"].append(self.accelerator.gather(mean_kl).nanmean().item())

        mean_entropy = masked_batch_mean(entropies)
        self._metrics[mode]["entropy"].append(self.accelerator.gather(mean_entropy).nanmean().item())

        # Compute the clipped probability ratios
        is_low_clipped = (coef_1 < 1 - self.epsilon_low) & (advantages.unsqueeze(1) < 0)
        is_high_clipped = (coef_1 > 1 + self.epsilon_high) & (advantages.unsqueeze(1) > 0)
        is_region_clipped = is_low_clipped | is_high_clipped

        low_clip = masked_batch_mean(is_low_clipped.float())
        high_clip = masked_batch_mean(is_high_clipped.float())
        clip_ratio = masked_batch_mean(is_region_clipped.float())

        gathered_low_clip = self.accelerator.gather(low_clip)
        self._metrics[mode]["clip_ratio/low_mean"].append(gathered_low_clip.nanmean().item())
        self._metrics[mode]["clip_ratio/low_min"].append(nanmin(gathered_low_clip).item())
        gathered_high_clip = self.accelerator.gather(high_clip)
        self._metrics[mode]["clip_ratio/high_mean"].append(gathered_high_clip.nanmean().item())
        self._metrics[mode]["clip_ratio/high_max"].append(nanmax(gathered_high_clip).item())
        gathered_clip_ratio = self.accelerator.gather(clip_ratio)
        self._metrics[mode]["clip_ratio/region_mean"].append(gathered_clip_ratio.nanmean().item())
        return loss

    def prediction_step(self, model, inputs, prediction_loss_only, ignore_keys: Optional[list[str]] = None):
        inputs = self._prepare_inputs(inputs)
        with torch.no_grad():
            with self.compute_loss_context_manager():
                loss = self.compute_loss(model, inputs)
            loss = loss.mean().detach()
        return loss, None, None

    def log(self, logs: dict[str, float], start_time: Optional[float] = None) -> None:
        mode = "train" if self.model.training else "eval"
        metrics = {key: sum(val) / len(val) for key, val in self._metrics[mode].items()}  # average the metrics

        # This method can be called both in training and evaluation. When called in evaluation, the keys in `logs`
        # start with "eval_". We need to add the prefix "eval_" to the keys in `metrics` to match the format.
        if mode == "eval":
            metrics = {f"eval_{key}": val for key, val in metrics.items()}

        logs = {**logs, **metrics}
        super().log(logs, start_time)
        self._metrics[mode].clear()

        if self.accelerator.is_main_process and self.log_completions:
            if is_rich_available():
                print_prompt_completions_sample(
                    self._logs["prompt"],
                    self._logs["completion"],
                    self._logs["rewards"],
                    self._logs["advantages"],
                    self.state.global_step,
                    self.num_completions_to_print,
                )

            if self.args.report_to and "wandb" in self.args.report_to and wandb.run is not None:
                import pandas as pd

                table = {
                    "step": [str(self.state.global_step)] * len(self._logs["prompt"]),
                    "prompt": self._logs["prompt"],
                    "completion": self._logs["completion"],
                    **self._logs["rewards"],
                    "advantage": self._logs["advantages"],
                }

                if self._logs["images"]:
                    table["images"] = []
                    for image_list in self._logs["images"]:
                        # Convert images to wandb Image objects for proper visualization
                        table["images"].append([wandb.Image(image) for image in image_list])

                df = pd.DataFrame(table)
                if self.wandb_log_unique_prompts:
                    df = df.drop_duplicates(subset=["prompt"])
                wandb.log({"completions": wandb.Table(dataframe=df)})

    # Ensure the model card is saved along with the checkpoint
    def _save_checkpoint(self, model, trial):
        if self.args.hub_model_id is None:
            model_name = Path(self.args.output_dir).name
        else:
            model_name = self.args.hub_model_id.split("/")[-1]
        self.create_model_card(model_name=model_name)
        super()._save_checkpoint(model, trial)
class UnslothGRPOTrainer(_UnslothGRPOTrainer):
    """
    
    Trainer for the Group Relative Policy Optimization (GRPO) method. This algorithm was initially proposed in the
    paper [DeepSeekMath: Pushing the Limits of Mathematical Reasoning in Open Language
    Models](https://huggingface.co/papers/2402.03300).

    Example:

    ```python
    from datasets import load_dataset
    from trl import GRPOTrainer

    dataset = load_dataset("trl-lib/tldr", split="train")
    def reward_func(completions, **kwargs):
        # Dummy reward function that rewards completions with more unique letters.
        return [float(len(set(completion))) for completion in completions]
    trainer = GRPOTrainer(
        model="Qwen/Qwen2-0.5B-Instruct",
        reward_funcs=reward_func,
        train_dataset=dataset,
    )

    trainer.train()
    ```

    Args:
        model (`Union[str, PreTrainedModel]`):
            Model to be trained. Can be either:

            - A string, being the *model id* of a pretrained model hosted inside a model repo on huggingface.co, or a
              path to a *directory* containing model weights saved using
              [`~transformers.PreTrainedModel.save_pretrained`], e.g., `'./my_model_directory/'`. The model is loaded
              using [`~transformers.AutoModelForCausalLM.from_pretrained`] with the keyword arguments in
              `args.model_init_kwargs`.
            - A [`~transformers.PreTrainedModel`] object. Only causal language models are supported.
        reward_funcs (`Union[RewardFunc, list[RewardFunc]]`):
            Reward functions to be used for computing the rewards. To compute the rewards, we call all the reward
            functions with the prompts and completions and sum the rewards. Can be either:

            - A single reward function, such as:
                - A string: The *model ID* of a pretrained model hosted inside a model repo on huggingface.co, or a
                path to a *directory* containing model weights saved using
                [`~transformers.PreTrainedModel.save_pretrained`], e.g., `'./my_model_directory/'`. The model is loaded
                using [`~transformers.AutoModelForSequenceClassification.from_pretrained`] with `num_labels=1` and the
                keyword arguments in `args.model_init_kwargs`.
                - A [`~transformers.PreTrainedModel`] object: Only sequence classification models are supported.
                - A custom reward function: The function is provided with the prompts and the generated completions,
                  plus any additional columns in the dataset. It should return a list of rewards. Custom reward
                  functions can also return `None` when the reward is not applicable to those samples. This is useful
                  for multi-task training where different reward functions apply to different types of samples. When a
                  reward function returns `None` for a sample, that reward function is excluded from the reward
                  calculation for that sample. For more details, see [Using a custom reward
                  function](#using-a-custom-reward-function).

                  The trainer's state is also passed to the reward function. The trainer's state is an instance of
                  [`~transformers.TrainerState`] and can be accessed by accessing the `trainer_state` argument to the
                  reward function's signature.
            - A list of reward functions, where each item can independently be any of the above types. Mixing different
            types within the list (e.g., a string model ID and a custom reward function) is allowed.
        args ([`GRPOConfig`], *optional*):
            Configuration for this trainer. If `None`, a default configuration is used.
        train_dataset ([`~datasets.Dataset`] or [`~datasets.IterableDataset`]):
            Dataset to use for training. It must include a column `"prompt"`. Any additional columns in the dataset is
            ignored. The format of the samples can be either:

            - [Standard](dataset_formats#standard): Each sample contains plain text.
            - [Conversational](dataset_formats#conversational): Each sample contains structured messages (e.g., role
              and content).
        eval_dataset ([`~datasets.Dataset`], [`~datasets.IterableDataset`] or `dict[str, Union[Dataset, IterableDataset]]`):
            Dataset to use for evaluation. It must meet the same requirements as `train_dataset`.
        processing_class ([`~transformers.PreTrainedTokenizerBase`], [`~transformers.ProcessorMixin`], *optional*):
            Processing class used to process the data. The padding side must be set to "left". If `None`, the
            processing class is loaded from the model's name with [`~transformers.AutoProcessor.from_pretrained`]. A
            padding token, `tokenizer.pad_token`, must be set. If the processing class has not set a padding token,
            `tokenizer.eos_token` will be used as the default.
        reward_processing_classes ([`~transformers.PreTrainedTokenizerBase`] or `list[PreTrainedTokenizerBase]`, *optional*):
            Processing classes corresponding to the reward functions specified in `reward_funcs`. Can be either:

            - A single processing class: Used when `reward_funcs` contains only one reward function.
            - A list of processing classes: Must match the order and length of the reward functions in `reward_funcs`.
            If set to `None`, or if an element of the list corresponding to a [`~transformers.PreTrainedModel`] is
            `None`, the tokenizer for the model is automatically loaded using
            [`~transformers.AutoTokenizer.from_pretrained`]. For elements in `reward_funcs` that are custom reward
            functions (not [`~transformers.PreTrainedModel`]), the corresponding entries in `reward_processing_classes`
            are ignored.
        callbacks (list of [`~transformers.TrainerCallback`], *optional*):
            List of callbacks to customize the training loop. Will add those to the list of default callbacks detailed
            in [here](https://huggingface.co/docs/transformers/main_classes/callback).

            If you want to remove one of the default callbacks used, use the [`~transformers.Trainer.remove_callback`]
            method.
        optimizers (`tuple[torch.optim.Optimizer, torch.optim.lr_scheduler.LambdaLR]`, *optional*, defaults to `(None, None)`):
            A tuple containing the optimizer and the scheduler to use. Will default to an instance of [`AdamW`] on your
            model and a scheduler given by [`get_linear_schedule_with_warmup`] controlled by `args`.
        peft_config ([`~peft.PeftConfig`], *optional*):
            PEFT configuration used to wrap the model. If `None`, the model is not wrapped.
    
    """
    def __init__(
        self,
        model,
        reward_funcs,
        args = None,
        train_dataset = None,
        eval_dataset = None,
        processing_class = None,
        reward_processing_classes = None,
        callbacks = None,
        peft_config = None,
        **kwargs
    ):
        if args is None: args = UnslothGRPOConfig()
        use_bf16 = getattr(args, 'bf16', False)
        if type(use_bf16) is not bool: use_bf16 = False
        use_fp16 = getattr(args, 'fp16', False)
        if type(use_fp16) is not bool: use_fp16 = False
        force_float32 = False
        try:
            from unsloth_zoo.device_type import device_is_bf16_supported as _bf16_supported
        except Exception:
            _bf16_supported = torch.cuda.is_bf16_supported
        full_finetuning = getattr(model, '_unsloth_full_finetuning', None)
        if full_finetuning is None: full_finetuning = os.environ.get('UNSLOTH_ENABLE_FULL_FINETUNING', '0') == '1'
        model_forced_float32 = getattr(model, '_unsloth_forced_float32', None)
        if model_forced_float32 is None: model_forced_float32 = os.environ.get('UNSLOTH_FORCE_FLOAT32', '0') == '1'
        if model_forced_float32 and not (full_finetuning and _bf16_supported()):
            print('Unsloth: Switching to float32 training since model cannot work with float16')
            force_float32 = True
        mixed_precision_dtype = os.environ.get('UNSLOTH_MIXED_PRECISION', 'float32')
        dtype = getattr(model.config, 'dtype', None) or getattr(model.config, 'torch_dtype', None)
        if dtype is None: dtype = model.get_input_embeddings().weight.dtype
        from unsloth_zoo.utils import _get_dtype
        dtype = _get_dtype(dtype)
        float16 = dtype == torch.float16
        bfloat16 = dtype == torch.bfloat16
        float32 = dtype == torch.float32
        user_float32 = bool(getattr(model, '_unsloth_user_float32', False))
        if full_finetuning:
            if bfloat16 and use_fp16: use_fp16 = False
            if float16 and use_bf16: use_bf16 = False
        if not force_float32 and (float16 and use_bf16): raise TypeError('Unsloth: Model is in float16 precision but you want to use bfloat16 precision. Set fp16 to `True` and bf16 to `False`')
        if not force_float32 and (bfloat16 and use_fp16): raise TypeError('Unsloth: Model is in bfloat16 precision but you want to use float16 precision. Set fp16 to `False` and bf16 to `True`')
        if force_float32:
            # Forced float32 training
            args.fp16 = False
            args.bf16 = False
            os.environ['ACCELERATE_MIXED_PRECISION'] = 'no'
            if hasattr(args, 'mixed_precision'): args.mixed_precision = 'no'
            # args.mixed_precision is a new argument which needs to be set now
        elif (not use_bf16 and not use_fp16) and mixed_precision_dtype == 'float32' and float32 and user_float32 and not _bf16_supported():
            print('Unsloth: Model is in float32 and this GPU has no bfloat16 support, so training stays in float32. Pass fp16 = True to force float16 mixed precision instead.')
            args.fp16 = False
            args.bf16 = False
            os.environ['ACCELERATE_MIXED_PRECISION'] = 'no'
            if hasattr(args, 'mixed_precision'): args.mixed_precision = 'no'
        elif (not use_bf16 and not use_fp16) and mixed_precision_dtype == 'float32':
            # Mixed precision training. bf16 only if the GPU supports it; V100/T4 use fp16.
            use_bf16_amp = (not float16) and _bf16_supported()
            args.fp16 = not use_bf16_amp
            args.bf16 = use_bf16_amp
            os.environ['ACCELERATE_MIXED_PRECISION'] = 'bf16' if use_bf16_amp else 'fp16'
            if hasattr(args, 'mixed_precision'): args.mixed_precision = 'bf16' if use_bf16_amp else 'fp16'
            # args.mixed_precision is a new argument which needs to be set now
        elif mixed_precision_dtype == 'bfloat16':
            # Both False since bfloat16 full finetuning doesn't do any autocasting.
            args.fp16 = False
            args.bf16 = False
            os.environ['ACCELERATE_MIXED_PRECISION'] = 'no'
            if hasattr(args, 'mixed_precision'): args.mixed_precision = 'no'
            # args.mixed_precision is a new argument which needs to be set now
        elif use_bf16 or use_fp16:
            # transformers <5 exported this itself from fp16/bf16; 5.x dropped the write, so an
            # explicit flag left it unset and GRPO readers defaulted to 'fp16', wrapping a
            # bfloat16 model in a float16 autocast. See unslothai/unsloth#4891.
            os.environ['ACCELERATE_MIXED_PRECISION'] = 'bf16' if use_bf16 else 'fp16'
            if hasattr(args, 'mixed_precision'): args.mixed_precision = 'bf16' if use_bf16 else 'fp16'
        
        if getattr(args, 'eval_dataset', None) is not None and getattr(args, 'eval_strategy', 'no') == 'no':
            args.eval_strategy = 'steps'
            if getattr(args, 'eval_steps', None) is None: args.eval_steps = 0.1
        ga_steps = getattr(args, 'gradient_accumulation_steps', None)
        if ga_steps is not None and ga_steps > 1:
            from transformers import __version__ as transformers_version
            if Version(transformers_version) <= Version('4.45.2'):
                print('**** Unsloth: Please use our fixed gradient_accumulation_steps by updating transformers, TRL and Unsloth!\n'
                      '`pip install --upgrade --no-cache-dir --force-reinstall --no-deps unsloth transformers trl unsloth_zoo`')
        if getattr(args, 'eval_strategy', 'no') != 'no':
            eval_bsz = getattr(args, 'per_device_eval_batch_size', 8)
            if eval_bsz == 8 and args.per_device_train_batch_size < eval_bsz: args.per_device_eval_batch_size = args.per_device_train_batch_size
            if getattr(args, 'eval_accumulation_steps', None) is None and ga_steps is not None: args.eval_accumulation_steps = ga_steps
        fp16_full_eval = getattr(args, 'fp16_full_eval', False)
        if type(fp16_full_eval) is not bool: fp16_full_eval = False
        bf16_full_eval = getattr(args, 'bf16_full_eval', False)
        if type(bf16_full_eval) is not bool: bf16_full_eval = False
        if args.fp16 and bf16_full_eval: args.bf16_full_eval = False; args.fp16_full_eval = True
        if args.bf16 and fp16_full_eval: args.bf16_full_eval = True; args.fp16_full_eval = False
        if force_float32:
            args.bf16_full_eval = False
            args.fp16_full_eval = False
        elif os.environ.get('UNSLOTH_MIXED_PRECISION', 'float32') == 'bfloat16':
            args.bf16_full_eval = True
            args.fp16_full_eval = False
        elif not bf16_full_eval and not fp16_full_eval:
            args.bf16_full_eval = args.bf16
            args.fp16_full_eval = args.fp16
        _output_logits = False
        if locals().get('compute_metrics', None) is not None: _output_logits = True
        if locals().get('preprocess_logits_for_metrics', None) is not None: _output_logits = True
        if _output_logits:
            os.environ['UNSLOTH_RETURN_LOGITS'] = '1'
        if model is not None:
            _warnings_issued = getattr(model, 'warnings_issued', None)
            if _warnings_issued is None:
                model.warnings_issued = {}
            elif not isinstance(_warnings_issued, dict):
                try:
                    model.warnings_issued = dict(_warnings_issued)
                except Exception:
                    model.warnings_issued = {}
        if 'max_seq_length' not in locals() and not hasattr(args, 'max_seq_length'):
            pass
        else:
            model_max_seq_length = getattr(model, 'max_seq_length', None)
            args_max_seq_length  = getattr(args,  'max_seq_length', None)
            if args_max_seq_length is None and model_max_seq_length is not None:
                max_seq_length = model.max_seq_length
                if hasattr(args, 'max_seq_length'): args.max_seq_length = max_seq_length
            elif args_max_seq_length is not None and model_max_seq_length is not None:
                if args_max_seq_length > model_max_seq_length:
                    print('Unsloth: You set `max_seq_length` as ' + str(args_max_seq_length) + ' but '
                           'the maximum the model supports is ' + str(model_max_seq_length) + '. We shall reduce it.')
                    args.max_seq_length = model_max_seq_length
        if model is not None and hasattr(model, 'for_training'):
            _use_gc = model._unsloth_gradient_checkpointing if hasattr(model, '_unsloth_gradient_checkpointing') else getattr(args, 'gradient_checkpointing', True)
            model.for_training(use_gradient_checkpointing=_use_gc)
        if 'tokenizer' in locals() and hasattr(tokenizer, 'padding_side'): tokenizer.padding_side = 'right'
        if 'processing_class' in locals():
            if hasattr(processing_class, 'padding_side'): processing_class.padding_side = 'right'
            if hasattr(processing_class, 'tokenizer') and hasattr(processing_class.tokenizer, 'padding_side'): processing_class.tokenizer.padding_side = 'right'
        other_metrics = []
        if not isinstance(reward_funcs, list): _reward_funcs = [reward_funcs]
        else: _reward_funcs = reward_funcs
        for reward_func in _reward_funcs:
            try:
                reward_func_name = reward_func.__name__
                if True:
                    other_metrics.append(f'rewards/{reward_func_name}/mean')
                if True:
                    other_metrics.append(f'rewards/{reward_func_name}/std')
                if False:
                    other_metrics.append(f'rewards/{reward_func_name}')
            except: pass
        
        from unsloth_zoo.logging_utils import PatchRLStatistics
        PatchRLStatistics('grpo_trainer', other_metrics)
        
        # [TODO] Fix up DataParallel multiplying batch sizes
        # [TODO] DDP works, but DP seems to not work? [TODO]
        if getattr(args, "parallel_mode", None) == ParallelMode.NOT_DISTRIBUTED and args.n_gpu > 1:
            if getattr(args, "_n_gpu", 1) != 1:
                args._n_gpu = 1
        if "model" in locals() and hasattr(model, "for_training"):
            _use_gc = model._unsloth_gradient_checkpointing if hasattr(model, '_unsloth_gradient_checkpointing') else getattr(args, 'gradient_checkpointing', True)
            model.for_training(use_gradient_checkpointing=_use_gc)
        super().__init__(
            model = model,
            reward_funcs = reward_funcs,
            args = args,
            train_dataset = train_dataset,
            eval_dataset = eval_dataset,
            processing_class = processing_class,
            reward_processing_classes = reward_processing_classes,
            callbacks = callbacks,
            peft_config = peft_config,**kwargs)
        if "model" in locals() and hasattr(model, "for_inference"):
            model.for_inference()
        if hasattr(self, 'neftune_hook_handle'):
            self.neftune_hook_handle.remove()
            if hasattr(self, 'neftune_hook_handle'): del self.neftune_hook_handle
        if getattr(args, 'neftune_noise_alpha', None) is not None:
            model.get_input_embeddings().neftune_noise_alpha = self.neftune_noise_alpha
        pass
        if hasattr(self, 'accelerator'):
            scaler = self.accelerator.scaler
            current_model = model
            while hasattr(current_model, 'model'):
                current_model.accelerator_scaler = scaler
                current_model = current_model.model
            current_model.accelerator_scaler = scaler
        pass
        if hasattr(self, 'train'):
            self.train = MethodType(prepare_for_training_mode(self.__class__.train), self)
        pass
        if hasattr(self, 'llm') and self.llm is not None and hasattr(self.llm, 'get_tokenizer'):
            _vllm_tok = self.llm.get_tokenizer()
            _pc = getattr(self, 'processing_class', None) or getattr(self, 'tokenizer', None)
            if _vllm_tok is not None and _pc is not None and getattr(_pc, 'chat_template', None) is not None and getattr(_vllm_tok, 'chat_template', None) is None:
                _vllm_tok.chat_template = _pc.chat_template
        pass
        
pass


if hasattr(logger, "addFilter"):
    import logging
    class HideLoggingMessage(logging.Filter):
        def __init__(self, text): self.text = text
        def filter(self, x): return not (self.text in x.getMessage())
    pass
    logger.addFilter(HideLoggingMessage("`use_cache=True`"))

