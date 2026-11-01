import cv2, numpy as np, sys, json
def refine(img_path, rough, iters=6, eps=2.0, min_area=200):
    img = cv2.imread(img_path); h, w = img.shape[:2]
    rough = np.array(rough, np.int32)
    mask = np.full((h, w), cv2.GC_BGD, np.uint8)
    cv2.fillPoly(mask, [rough], cv2.GC_PR_FGD)
    # definite foreground: rough polygon shrunk
    inner = np.zeros((h, w), np.uint8); cv2.fillPoly(inner, [rough], 255)
    k = max(3, int(min(w, h) * 0.012))
    inner = cv2.erode(inner, np.ones((k, k), np.uint8), iterations=2)
    mask[inner > 0] = cv2.GC_FGD if False else cv2.GC_PR_FGD
    bgd = np.zeros((1, 65), np.float64); fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(img, mask, None, bgd, fgd, iters, cv2.GC_INIT_WITH_MASK)
    m = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cs = [c for c in cs if cv2.contourArea(c) >= min_area]
    if not cs: return None, m
    c = max(cs, key=cv2.contourArea)
    ap = cv2.approxPolyDP(c, eps, True)[:, 0, :]
    return ap.tolist(), m
