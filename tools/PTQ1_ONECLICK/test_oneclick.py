"""Synthetic fixtures exercise the runner; never device measurements."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
import ptq1_oneclick as b

IDENTITY = {"source_git_sha": "a"*40, "build_number": "114", "official_model": {"sha256": "b"*64, "size_bytes": 5946648928}}
CONFIG = {"context":16384,"batch":16,"kv":"Q4_0","flags":0}
def sample(flags=0):
    actual={"context":16384,"batch":16,"ubatch":16,"kv_k":"Q4_0","kv_v":"Q4_0","flags":flags,"flash_attention":True,"sequence_max":1,"kv_reuse":False}
    native=dict(actual,model_identity=IDENTITY["official_model"])
    delta=[0]*10;delta[6]=delta[7]=10
    if flags&1:delta[:3]=[2,2,2]
    if flags&2:delta[3:6]=[2,2,2]
    operations=[]
    for mask,arm,pipeline in [(1,'tensor','kernel_mul_mm_ptq1_tensorops_0_f32'),(2,'fused','kernel_mul_mv_ptq1_0_f32_bonsai_r5')]:
        if flags&mask:operations.append(dict(arm=arm,pipeline=pipeline,K=5120,M=16 if mask==1 else 1,N=5120,
            weight_nb0=38,weight_nb1=1520,activation_nb0=4,activation_nb1=20480,output_nb0=4,output_nb1=20480))
    return {"actual":actual,"evidence":{"source_git_sha":"a"*40,"build_number":"114","process_id":"p","native_context":native},
      "operation_evidence":operations,"counter_delta":delta,"gpu_completion_drained":True,"prompt_tokens":2048,"generated_tokens":128,"effective_max_tokens":128,
      "prefill_s":20.,"ttft_s":20.1,"decode_tps":10.,"client_first_content_s":20.2,"client_final_answer_s":20.2,
      "client_first_sse_s":.01,"wall_s":33.,"finish_reason":"length","output_sha256":"c"*64,
      "logits_probe":{"finite":True,"top1":7,"sample":[.1,.2]},"batch_allocations":2,"batch_reuses":200 if flags&4 else 0,
      "memory":{"sampled_peak_footprint_bytes":7*b.GIB,"min_available_bytes":b.GIB,"max_thermal_state":0,"samples":20},
      "stage":"formal","repeat":0,"prompt_hash":"d"*64,"target_tokens":2048,"valid":True}
class Tests(unittest.TestCase):
    def test_execution_proof_is_more_than_enqueue(self):
        s=sample(1);config=dict(CONFIG,flags=1)
        self.assertEqual(b.validate_sample(s,config,IDENTITY),[])
        s["counter_delta"][7]=0
        self.assertIn("gpu_completion",b.validate_sample(s,config,IDENTITY))
        s=sample(1);s["counter_delta"][2]=0
        self.assertIn("tensor_dispatch",b.validate_sample(s,config,IDENTITY))
    def test_actual_shape_identity_and_model_are_required(self):
        for field,value in [("batch",8),("kv_k","Q8_0"),("sequence_max",2)]:
            s=sample();s["evidence"]["native_context"][field]=value
            self.assertTrue(b.validate_sample(s,CONFIG,IDENTITY))
        s=sample();s["evidence"]["source_git_sha"]="other"
        self.assertIn("source_identity",b.validate_sample(s,CONFIG,IDENTITY))
    def test_strict_comparison_no_lowered_gates(self):
        base=[sample() for _ in range(3)];cand=copy.deepcopy(base)
        for i,(x,y) in enumerate(zip(base,cand)):
            x["repeat"]=y["repeat"]=i;y["prefill_s"]=16.;y["ttft_s"]=17.;y["client_first_content_s"]=17.
        self.assertEqual(b.compare_samples(base,cand)["status"],"PERFORMANCE_PASS")
        cand[0]["output_sha256"]="different"
        self.assertEqual(b.compare_samples(base,cand)["status"],"INCOMPLETE")
        cand=copy.deepcopy(base)
        self.assertEqual(b.compare_samples(base,cand)["status"],"NO_GAIN")
        self.assertEqual(b.compare_samples(base[:2],cand)["status"],"INCOMPLETE")
    def test_sse_meta_is_not_first_content(self):
        clock=iter([.01,.3,.5,.6])
        data=b'event: meta\ndata: {}\n\nevent: delta\ndata: {"content":"answer"}\n\nevent: result\ndata: {"text":"answer"}\n\n'
        r=b.read_sse(io.BytesIO(data),0.,clock=lambda:next(clock))
        self.assertEqual(r["client_first_sse_s"],.01)
        self.assertEqual(r["client_first_content_s"],.3)
        self.assertEqual(r["client_final_answer_s"],.3)
    def test_eof_without_result_is_uncertain(self):
        with self.assertRaises(b.UncertainRequest):
            b.read_sse(io.BytesIO(b'event: meta\ndata: {}\n\n'),0.,clock=lambda:1.)
    def test_quality_code_exec_is_restricted(self):
        good='def sum_even(n):\n    return sum(range(0, n+1, 2))'
        self.assertTrue(b.check_code(good))
        self.assertTrue(b.check_code('def sum_even(n: int) -> int:\n    \"\"\"Sum even integers.\"\"\"\n    return sum(range(0,n+1,2))'))
        self.assertFalse(b.check_code('import os\nos.remove("x")'))
        self.assertFalse(b.check_code('def sum_even(n):\n    return ().__class__'))
    def test_redaction_and_result_zip(self):
        with tempfile.TemporaryDirectory() as d:
            report={"status":"INCOMPLETE","samples":[dict(sample(),text="PRIVATE",prompt="SECRET",api_key="KEY")],"errors":[]}
            b.write_reports(Path(d),report)
            contents=(Path(d)/'report.json').read_text(encoding='utf-8')
            self.assertNotIn('PRIVATE',contents);self.assertNotIn('SECRET',contents);self.assertNotIn('KEY',contents)
            import zipfile
            with zipfile.ZipFile(Path(d)/'results.zip') as z:self.assertIsNone(z.testzip())
if __name__=='__main__':unittest.main()
