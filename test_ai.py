import numpy as np
from ai_similarity import similarity
x=np.array([1.,0.]); y=np.array([0.,1.])
assert abs(similarity(x,x)-1)<1e-6
assert abs(similarity(x,y))<1e-6
from online_audio import rank_candidates
import inspect
assert 'engine' in inspect.signature(rank_candidates).parameters
print('AI interface smoke test passed')
