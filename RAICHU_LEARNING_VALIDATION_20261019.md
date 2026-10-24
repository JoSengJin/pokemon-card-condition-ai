# 라이츄 라벨 반영 · 모서리 최초 양음성 학습 · 엣지 대조 — 2026-10-19

## 직접 결과
라이츄 1·3번은 corner_defect0, 2·4번은 edge_defect1로 저장했다. 2번 마모는 위쪽 평평한 끝선, 4번은 해당 확대그림 안 왼쪽 아래 끝선이다. corner2/4 및 edge1/3은 미확인으로 유지했다. W는미확인제외·X/Y는corner1로유지. 실제점좌표를추정생성하지않았다.

모서리 정상0→2구간(한그룹), 양성19구간(실제점14+존재5). 기존 detail fitter로21학습bag 혼합감독이 실제수렴(train objective .0628223,maxgrad3.88e-7)했고 연구head1개를 저장했다. 이는 학습구현검증이며 독립 정확도 개선이 아니다. 정상카드그룹이1개라 해당카드를heldout하면학습정상0이되어완전한group검증이불가함을감사했다. 실제양성만남은입력으로 optimizer가시작되지않는guard를확인했다.

엣지 대조2개는추가성능없음: 같은26구간(손상4/정상22), 기존최대반응기준·라이츄존재감독2추가·종류별groupmass 세경로모두FN0/4·FP3/22(13.64%)·실제점누락0/4. 변화0%p·새오류0·복구0. U/V도TP1/FP1 그대로. 엣지후보둘다미채택. 운영모델/기본값/Gemini/OpenCV변경없음.

## 실행 가설과 확인한 원인 범위
1. **양음성 corner seed**: 정상1/3만0으로추가했고2/4를모서리손상으로만들지않았다. DINO448은frozen, L2=1, 기존mean_odds 기본손실, 실제point14와지역존재5를구분했다. 여섯신규구간특징만추출하고기존15cache의사진별ID를대조해재사용했다. 실제점외의양성픽셀을정상/손상으로전파하지않았다.
2. **존재감독 edge**: 기존57풀에지역존재양성2만추가한59풀, 최대반응정상손실·기존실제점·L2=1·threshold.5·그룹/클래스정책고정. 3matched control은기존point fitter와계수차0. 후보3fit수렴했지만같은26개/UV에서추가개선없음. 나중에고정기준을새지역에대조하니보강전부터각3head가모두경고하고있었다(.71~.93). 학습후.94~.97반응은학습적합이지새누락복구가아니다. 최대반응이실제마모위치임을증명하지도않는다. 향후사진보강전고정기준오류/자료공백을먼저검사해야한다.
3. **종류별 group mass**: 기존 count(group) 분모는한실물전체가중치를균등하게하고, 양음성이함께있으면종류별가중치가나뉜다. 기존M/N은각.5,꼬렛정상2곳합.667/손상1곳.333이었다(class balancing전). 후보는 count(target,group)로종류내각실물합1이되도록한뒤종류총합을균등화했다. 두정책의목표가다르므로기존방식을버그로단정하지않는다. 같은57풀/입력/손실/기준에서3fit수렴했지만변화0으로정책미변경.
4. **학습적합의지름길 대조**: 같은21학습crop의평균RGB3값만사용한학습대조도19/21(손상17/19·정상2/2)을맞혔다. 정상은금색뒷면한실물에집중돼있다. 모델이실제로색만본다는인과증거는아니지만, 학습적합만으로미세마모표현력을배웠다고할수없는근거다. 정상그룹/뒷면형식다양성및별도독립평가필요.

## 변경 파일 / 핵심 diff
- card_condition/detail_bag.py: `normal_reduction='mean_odds'` 기본유지, opt-in `max_bound`를기존 point_bag_loss로전달. mixed point/presence에서도기존edge정상목표를바꾸지않고사용가능. 실제점/존재감독의정의는유지.
- tests/test_detail_bag.py: max_bound에서실제점/존재/padding gradient보존, all-point입력에서point fitter와실제적합계수동일성·unknown옵션거부2검사추가.
- artifacts/raichu-corner-seed-20261019/: 직접답변·2/4명확화·file/decoded SHA와fullback anchor 검증된row·group coverage·학습전계획·21bagcache/head·실행결과·원본검증·RGB지름길대조·default소스호환대조·36tests.
- artifacts/raichu-edge-presence-20261019/: 지역존재2행학습/3fold대조·저장재현·신규2원본재현·새자료기존경고감사.
- artifacts/edge-class-group-balance-20261019/: 종류별그룹mass 단일가설·각fold종류내그룹합1assert·3수렴fit·재현·미채택.
- artifacts/raichu-learning-review-20261019/: 모서리21학습사진반응과엣지26개대조사진/정답/원본결과링크를담은HTML. 학습과품질평가를구분.
- artifacts/raichu-edge-presence-20261019/normal-edge-review/: 아직미확인인같은사진다른직선5/6의원본1:1·전체위치·정답null. 현재유효기준3head를질문전에SHA고정하고예측을숨김. train용자료이며독립시험으로세지않음.
- 본문서 및 소비 프로젝트 CONDITION_ANALYSIS_TODO.md: 현재체크포인트.

## 검증
- 실제공용detail_data로fullback anchor/파일SHA/decoded동일성/group/split 검증. 최신clarified rows9=corner1존재5+corner0구간2+edge1존재2. W/corner2/corner4미확인skip. labels종류전파0,정확점생성0.
- 모서리원본21forward·21구간출력·14실제점출력/좌표token매핑·21mask 모두차이0. 새6특징forward와이전14정확점/1presence cache 일치.
- 정상onlygroup을뺀양성only실제입력fitter거부. qualityfold누출을허용하지않음.
- 공용옵션연결후원래corner21기본fit계수/절편차이0(source-compatibility.json). 기존corner검증실행뒤소스에옵션을추가했으며이력SHA를구분했다. 이전학습계획checksum을새소스에맞춰고치지않음.
- edge3matched controls 실제계수차0. 후보26cache출력/실제점4/UV6fold 재실행차0. 신규원본2MPSforward에서추가bag6학습출력/특징/마스크차0(verification.json).
- class-group후보26/실제점4/UV6출력재실행차0,모든fold별종류내groupmass1assert.
- 관련unittest36개통과. canonical70행SHA불변. HTML local사진/문서링크검사. 브라우저자동열기/렌더검증은수행하지않았고사진은로컬뷰어로확인했다.

## 다음 작업과 사람 의존
1/3모서리정상·2/4직선엣지손상은완료했으므로재요청하지않는다. 같은사진의다른위치인좌측중간직선5/우측중간직선6만정상/손상/판독어려움을확인할수있게준비했다. 같은금색무늬/촬영에서정상끝선과손상을함께비교할입력근거가현재없기때문이다. 모서리정상을새위치의정상엣지로복사하지않는다. 5/6은추론계획고정뒤2forward만수행했고정답생성/학습0. 코너품질에는다른실물정상그룹과파란뒷면정상확인이추가로필요하며현재정상한그룹을복제해채우지않는다.

## 리스크 / 롤백
Corner정상1그룹과다른카드양성19로색·배경지름길위험이높아운영채택금지. 새로운edge존재bag는실제점지도아니므로국소화성공주장금지. 반복26개개발평가의숫자는독립일반화근거가아님. RGB대조의학습19/21을제품정확도로보고하지않음.

공용기본유지이므로기존호출은원래동작한다. 옵션연결롤백은detail_bag의normal_reduction인자/전달/검증과2새테스트만되돌린다. 이번3연구checkpoint후보를사용하지않으면운영은원래상태다. 새모서리head는연구학습smoke용이고엣지후보는모두미채택이다. 사람확인정답과원시계획/결과는삭제·변경하지않는다.
