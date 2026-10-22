// Generated from the "종족별 진화표" (Evolutions) board of the Token Pet design canvas.
// The data and form rules below are copied verbatim; only the module wrapper and the
// render function at the bottom are new. 64x64 grid, rects are [x, y, w, h, color, opacity?].
/* eslint-disable */
var D = '#23203A', W = '#F4F1FF', G = '#F5C451', P = '#F38BA3', LG = '#FFE59A';
    function mix(a, b, t) {
      var pa = [1, 3, 5].map(function (i) { return parseInt(a.substr(i, 2), 16); });
      var pb = [1, 3, 5].map(function (i) { return parseInt(b.substr(i, 2), 16); });
      return '#' + pa.map(function (v, i) {
        var n = Math.round(v + (pb[i] - v) * t);
        return (n < 16 ? '0' : '') + n.toString(16);
      }).join('');
    }
    function outline(x, y, w, h, c) {
      return [[x, y, w, 1, c], [x, y + h - 1, w, 1, c], [x, y, 1, h, c], [x + w - 1, y, 1, h, c]];
    }
    function eye(box, draw, shine) { return { box: box, draw: draw, shine: shine || [] }; }

    var S = [
      { key: 'mochi', name: '모찌', part: '기준 종족', cx: 32, hatY: 24, mouthY: 44, item: [52, 44], primary: ['#FFB7C5'], ink: D,
        body: [[16,26,32,26,'#FFB7C5'],[14,30,36,18,'#FFB7C5'],[18,52,28,4,'#FFB7C5'],[12,24,8,8,'#FFB7C5'],[44,24,8,8,'#FFB7C5'],[14,26,4,4,P],[46,26,4,4,P],[18,42,5,3,P],[41,42,5,3,P],[29,44,6,2,D],[22,56,8,4,P],[34,56,8,4,P]],
        eyes: [eye([22,36,5,6],[[22,36,5,6,D]],[[23,37,2,2,W]]), eye([37,36,5,6],[[37,36,5,6,D]],[[38,37,2,2,W]])] },
      { key: 'squirrel', name: '결정 다람쥐', part: '꼬리 결정', cx: 26, hatY: 18, mouthY: 40, item: [0, 46], primary: ['#C97A4A'], ink: D,
        body: [[42,30,6,22,G],[46,18,8,30,G],[50,10,8,24,G],[52,6,4,6,LG],[48,22,4,4,'#9A6E12'],[52,30,4,4,'#9A6E12'],[44,38,4,4,'#9A6E12'],[12,26,30,26,'#C97A4A'],[10,30,34,18,'#C97A4A'],[12,18,6,10,'#C97A4A'],[34,18,6,10,'#C97A4A'],[14,12,2,6,'#6FE3B3'],[12,10,6,2,'#6FE3B3'],[36,12,2,6,'#6FE3B3'],[34,10,6,2,'#6FE3B3'],[16,38,20,12,'#FFF0DC'],[24,40,4,2,D],[8,38,8,8,G],[10,40,4,4,LG],[16,52,6,4,'#9A5A32'],[30,52,6,4,'#9A5A32']],
        eyes: [eye([18,32,5,5],[[18,32,5,5,D]],[[19,33,2,2,G]]), eye([29,32,5,5],[[29,32,5,5,D]],[[30,33,2,2,G]])] },
      { key: 'mole', name: '두더지', part: '안전모 램프', cx: 32, hatY: 8, mouthY: 38, item: [54, 30], primary: ['#6B5A7A'], ink: D,
        body: [[6,46,52,12,'#3A3660'],[10,44,44,4,'#4A4677'],[16,22,32,26,'#6B5A7A'],[14,26,36,18,'#6B5A7A'],[22,36,20,10,'#B89AC4'],[29,32,6,5,P],[14,14,36,8,G],[18,8,28,6,G],[28,10,8,4,W],[8,38,8,8,'#B89AC4'],[48,38,8,8,'#B89AC4'],[10,44,2,2,G],[52,42,2,2,G]],
        eyes: [eye([22,30,3,3],[[22,30,3,3,D]]), eye([39,30,3,3],[[39,30,3,3,D]])] },
      { key: 'robot', name: '굴뚝 로봇', part: '배 속 화로', cx: 32, hatY: 2, mouthY: 32, item: [52, 48], primary: ['#8FB4FF', '#5B8FE8'], ink: '#6FE3B3',
        body: [[26,4,12,12,'#5F5B82'],[24,2,16,3,'#5F5B82'],[30,0,2,2,'#A9A3C9'],[14,16,36,22,'#8FB4FF'],[12,20,40,14,'#8FB4FF'],[18,20,12,10,'#1C1A2E'],[34,20,12,10,'#1C1A2E'],[26,32,12,2,'#5F5B82'],[16,38,32,18,'#5B8FE8'],[22,42,20,10,'#1C1A2E'],[24,44,6,6,'#F5A54A'],[31,45,3,4,G],[35,44,2,2,G],[38,47,2,2,G],[6,40,10,6,'#8FB4FF'],[48,40,10,6,'#8FB4FF'],[4,38,4,10,'#5F5B82'],[56,38,4,10,'#5F5B82'],[18,56,8,6,'#5F5B82'],[38,56,8,6,'#5F5B82']],
        eyes: [eye([18,20,12,10],[[23,22,2,6,'#6FE3B3'],[25,24,2,2,'#6FE3B3']]), eye([34,20,12,10],[[39,22,2,6,'#6FE3B3'],[41,24,2,2,'#6FE3B3']])] },
      { key: 'penguin', name: '별가루 펭귄', part: '배의 초승달', cx: 32, hatY: 4, mouthY: 26, item: [52, 44], primary: ['#2A2F6B'], ink: D,
        body: [[18,10,28,46,'#2A2F6B'],[14,18,36,32,'#2A2F6B'],[20,14,2,2,W],[40,26,2,2,W],[16,34,2,2,W],[44,42,2,2,W],[22,28,20,24,'#D9D4F5'],[28,34,8,12,G],[32,36,6,8,'#D9D4F5'],[22,18,5,5,W],[37,18,5,5,W],[29,22,6,4,LG],[28,23,8,2,G],[26,4,4,6,G],[28,2,4,2,G],[8,24,6,18,'#2A2F6B'],[50,24,6,18,'#2A2F6B'],[10,38,2,2,W],[20,56,8,4,'#F5A54A'],[36,56,8,4,'#F5A54A']],
        eyes: [eye([22,18,5,5],[[24,20,2,2,'#8FB4FF']]), eye([37,18,5,5],[[39,20,2,2,P]])] },
      { key: 'hamster', name: '유리볼 햄스터', part: '투명 볼주머니', cx: 32, hatY: 10, mouthY: 40, item: [0, 50], primary: ['#F5D9A8'], ink: D,
        body: [[14,22,36,30,'#F5D9A8'],[10,28,44,18,'#F5D9A8'],[14,14,8,10,'#F5D9A8'],[42,14,8,10,'#F5D9A8'],[22,10,6,8,'#F5D9A8'],[36,10,6,8,'#F5D9A8'],[16,16,4,6,P],[44,16,4,6,P],[24,12,2,4,P],[38,12,2,4,P],[6,30,12,14,'#C9E8FF',0.8],[46,30,12,14,'#C9E8FF',0.8],[8,34,3,3,G],[12,38,3,3,G],[48,36,3,3,G],[53,32,3,3,G],[51,40,2,2,G],[30,36,4,3,P],[28,40,8,2,D],[50,48,6,2,'#C9A23A'],[56,44,4,6,LG],[57,45,2,4,G],[18,52,8,4,'#E0BC7A'],[38,52,8,4,'#E0BC7A']],
        eyes: [eye([22,30,5,6],[[22,30,5,6,D]],[[23,31,2,2,W]]), eye([37,30,5,6],[[37,30,5,6,D]],[[38,31,2,2,W]])] },
      { key: 'rabbit', name: '안테나 토끼', part: '회로선 · 세 번째 눈', cx: 31, hatY: 26, mouthY: 44, item: [52, 30], primary: ['#D9D4F5'], ink: D,
        body: [[18,2,6,24,'#D9D4F5'],[19,0,4,2,'#6FE3B3'],[20,6,2,16,P],[38,10,6,16,'#D9D4F5'],[42,6,8,6,'#D9D4F5'],[48,4,4,4,G],[40,14,2,10,P],[16,26,30,26,'#D9D4F5'],[14,30,34,18,'#D9D4F5'],[29,30,4,4,D],[30,31,2,2,'#6FE3B3'],[29,42,4,2,P],[27,44,8,2,D],[16,44,2,6,'#8FB4FF'],[16,48,6,2,'#8FB4FF'],[44,40,2,8,'#8FB4FF'],[40,40,6,2,'#8FB4FF'],[42,46,2,2,'#6FE3B3'],[18,52,8,6,'#B8B2E0'],[36,52,8,6,'#B8B2E0'],[46,48,6,6,W]],
        eyes: [eye([20,34,5,6],[[20,34,5,6,D]],[[21,35,2,2,W]]), eye([36,34,5,6],[[36,34,5,6,D]],[[37,35,2,2,W]])] }
    ];

    // 종족 고유 진화: n=이름, sw=색 교체(원본색→새색), drop=지울 원본색, over=추가 픽셀('T'=그 형태로 물든 몸색)
    var SIG = {
      squirrel: {
        base: { n: '도토리' },
        model: { n: '반듯한 결정', over: [[47,20,1,24,W],[51,12,1,20,W]] },
        miser: { n: '결정 산더미', over: [[54,40,8,12,G],[58,36,4,6,LG],[40,50,10,6,G],[44,48,4,2,LG]] },
        owl: { n: '야광 결정', sw: { '#F5C451': '#8FB4FF', '#FFE59A': '#C9E8FF' } },
        spender: { n: '보석 꼬리', over: [[48,24,3,3,P],[52,16,3,3,'#6FE3B3'],[46,34,3,3,'#8FB4FF'],[54,8,2,2,W]] },
        thug: { n: '깨진 결정', sw: { '#F5C451': '#9A6E12' }, over: [[50,14,1,10,D],[47,28,1,8,D],[53,34,1,6,D]] },
        runaway: { n: '결정 조각만', over: [[30,48,4,6,G],[31,46,2,2,LG]] },
        scholar: { n: '결정 렌즈', over: [[50,10,8,8,'#C9E8FF',0.8],[52,12,2,2,W]] },
        burnout: { n: '탁한 결정', sw: { '#F5C451': '#8A8070', '#FFE59A': '#A9A3A0' } },
        tycoon: { n: '황금 꼬리', sw: { '#9A6E12': '#FFE59A' }, over: [[52,0,6,4,LG],[60,8,2,2,W],[42,16,2,2,W]] },
        loanshark: { n: '저당 잡힌 꼬리', over: [[56,26,7,5,W],[57,28,1,1,D],[59,28,3,1,D]] },
        hunter: { n: '발광 꼬리', sw: { '#F5C451': '#6FE3B3', '#FFE59A': '#C9FFE8' } },
        vampire: { n: '핏빛 결정', sw: { '#F5C451': '#C0405A', '#FFE59A': '#F38BA3' } },
        influencer: { n: '반짝 꼬리', sw: { '#FFE59A': '#F4F1FF' }, over: [[60,4,2,2,W],[40,8,2,2,W],[60,30,2,2,W],[38,22,1,1,W]] },
        broke: { n: '텅 빈 꼬리', sw: { '#F5C451': '#4A4677', '#FFE59A': '#5F5B82', '#9A6E12': '#3A3660' } },
        boss: { n: '가시 결정', sw: { '#F5C451': '#C9A23A' }, over: [[58,14,5,4,'#C9A23A'],[56,26,7,3,'#C9A23A'],[39,24,3,4,'#C9A23A']] }
      },
      mole: {
        base: { n: '새내기 광부' },
        model: { n: '안전수칙 헬멧', over: [[14,18,36,2,'#F5A54A']] },
        miser: { n: '광석 자루', over: [[2,40,4,4,'#8FB4FF'],[6,42,4,4,G],[4,38,3,3,'#6FE3B3']] },
        owl: { n: '야간 램프', sw: { '#F4F1FF': '#8FB4FF' }, over: [[24,0,16,8,'#8FB4FF',0.35]] },
        spender: { n: '꽃 헬멧', over: [[42,4,4,4,P],[44,2,2,2,LG],[18,4,3,3,'#6FE3B3']] },
        thug: { n: '찌그러진 헬멧', sw: { '#F5C451': '#9A6E12', '#F4F1FF': '#5F5B82' }, over: [[20,8,6,3,'#2D2A4A']] },
        runaway: { n: '헬멧만 남음', over: [[24,44,16,6,G],[28,40,8,4,G],[30,42,4,2,W]] },
        scholar: { n: '탐사 돋보기', over: [[44,2,9,9,'#C9E8FF',0.7],[52,10,2,4,'#5F5B82']] },
        burnout: { n: '꺼진 램프', sw: { '#F4F1FF': '#3A3660' }, over: [[50,20,2,4,'#8FB4FF'],[12,24,2,3,'#8FB4FF']] },
        tycoon: { n: '황금 드릴', over: [[30,0,4,8,LG],[31,-4,2,4,LG],[29,2,6,1,'#9A6E12']] },
        loanshark: { n: '광산 소유권', over: [[50,22,12,9,W],[52,24,8,1,D],[52,27,6,1,D]] },
        hunter: { n: '탐조등', sw: { '#F4F1FF': '#6FE3B3' }, over: [[22,-6,20,14,'#6FE3B3',0.3]] },
        vampire: { n: '어둠의 굴', sw: { '#3A3660': '#3A2A3A', '#4A4677': '#5A2A3A' } },
        influencer: { n: '무대 조명', over: [[20,-8,24,56,LG,0.18]] },
        broke: { n: '빈 광차', over: [[46,48,14,6,'#5F5B82'],[48,54,3,3,D],[56,54,3,3,D]] },
        boss: { n: '광산 두목', sw: { '#F5C451': '#23203A', '#F4F1FF': '#F05A3A' } }
      },
      robot: {
        base: { n: '시제품' },
        model: { n: '정시 가동', over: [[30,-4,4,3,'#A9A3C9'],[40,16,6,4,W],[42,17,1,2,D]] },
        miser: { n: '금고 배', sw: { '#1C1A2E': '#3A3660' }, over: [[30,45,4,4,G],[31,43,2,2,G]] },
        owl: { n: '야간 모드', over: [[28,-6,2,2,W],[34,-9,2,2,W],[38,-4,1,1,W]] },
        spender: { n: '네온 튜닝', over: [[12,34,40,1,P],[16,55,32,1,'#6FE3B3'],[24,2,16,1,P]] },
        thug: { n: '고장 난 굴뚝', over: [[36,0,8,4,'#5F5B82'],[38,-6,4,4,D],[42,-10,3,3,D]] },
        runaway: { n: '톱니만 남음', over: [[26,46,8,8,'#5F5B82'],[28,48,4,4,D],[29,44,2,2,'#5F5B82'],[29,54,2,2,'#5F5B82']] },
        scholar: { n: '연산 안테나', over: [[22,-4,20,3,'#A9A3C9'],[31,-7,2,3,'#6FE3B3']] },
        burnout: { n: '과열', sw: { '#F5A54A': '#F05A3A' }, over: [[26,-6,6,6,D],[34,-11,6,6,D]] },
        tycoon: { n: '황금 굴뚝', sw: { '#5F5B82': '#F5C451' } },
        loanshark: { n: '계산기 배', over: [[24,44,2,2,W],[28,44,2,2,W],[32,44,2,2,W],[24,48,2,2,W],[28,48,2,2,W],[32,48,2,2,W],[36,44,4,6,G]] },
        hunter: { n: '서치라이트', over: [[30,-3,4,3,'#6FE3B3'],[26,-10,12,7,'#6FE3B3',0.3]] },
        vampire: { n: '배터리 흡혈', over: [[56,48,8,2,'#5F5B82'],[62,44,2,6,P]] },
        influencer: { n: '홀로그램', over: [[44,0,14,10,'#8FB4FF',0.4],[48,3,6,4,W,0.7]] },
        broke: { n: '꺼진 화로', sw: { '#F5A54A': '#3A3660', '#F5C451': '#5F5B82' } },
        boss: { n: '중장갑', over: [[10,18,6,16,'#3A3660'],[48,18,6,16,'#3A3660'],[16,38,32,3,'#3A3660']] }
      },
      penguin: {
        base: { n: '아기 별' },
        model: { n: '반달', over: [[16,14,2,2,W],[46,20,2,2,W]] },
        miser: { n: '달 저금통', over: [[27,33,11,14,G],[30,36,5,1,D]] },
        owl: { n: '보름달', over: [[27,33,11,14,LG],[29,36,3,3,'#F5C451']] },
        spender: { n: '은하 무늬', over: [[16,22,2,2,P],[44,18,2,2,'#6FE3B3'],[18,46,2,2,LG],[46,30,2,2,P],[24,10,2,2,'#8FB4FF']] },
        thug: { n: '그믐', over: [[28,34,8,12,'#D9D4F5'],[28,36,2,8,'#9A6E12']] },
        runaway: { n: '별 하나만', over: [[30,48,3,3,W],[28,49,7,1,W],[31,46,1,7,W]] },
        scholar: { n: '별자리', over: [[20,14,21,1,'#8FB4FF'],[40,14,1,13,'#8FB4FF'],[16,27,25,1,'#8FB4FF']] },
        burnout: { n: '흐린 밤', over: [[12,10,14,6,'#5F5B82'],[38,24,12,5,'#5F5B82'],[14,40,10,4,'#5F5B82']] },
        tycoon: { n: '황금 일식', over: [[26,32,14,1,G],[26,47,14,1,G],[26,32,1,16,G],[39,32,1,16,G]] },
        loanshark: { n: '달 저당', over: [[40,34,7,5,W],[41,36,4,1,D]] },
        hunter: { n: '사냥 달', sw: { '#F5C451': '#6FE3B3' } },
        vampire: { n: '핏빛 달', sw: { '#F5C451': '#C0405A' } },
        influencer: { n: '스타', over: [[13,11,4,4,W],[44,40,4,4,W],[40,24,3,3,W],[14,11,2,6,W],[12,13,6,2,W]] },
        broke: { n: '별 팔아버림', over: [[20,14,2,2,'T'],[40,26,2,2,'T'],[16,34,2,2,'T'],[44,42,2,2,'T'],[10,38,2,2,'T']] },
        boss: { n: '흑월', sw: { '#F5C451': '#5F5B82' } }
      },
      hamster: {
        base: { n: '빈 볼' },
        model: { n: '알맞은 볼', over: [[8,40,3,3,G],[49,42,3,3,G]] },
        miser: { n: '빵빵 볼', over: [[3,27,15,19,'#C9E8FF',0.8],[46,27,15,19,'#C9E8FF',0.8],[5,30,3,3,G],[9,32,3,3,G],[6,40,3,3,G],[54,38,3,3,G],[56,30,3,3,G],[50,30,3,3,G]] },
        owl: { n: '야광 볼', sw: { '#F5C451': '#8FB4FF', '#FFE59A': '#C9E8FF' } },
        spender: { n: '볼 터치', sw: { '#C9E8FF': '#FFC9DA' }, over: [[16,8,4,4,P],[17,6,2,2,LG]] },
        thug: { n: '이쑤시개', over: [[36,40,11,1,'#C9A23A'],[46,39,2,1,'#C9A23A']] },
        runaway: { n: '해바라기씨만', over: [[24,50,3,3,G],[30,52,3,3,G],[36,50,3,3,G],[42,52,3,3,G]] },
        scholar: { n: '볼 속 문서', over: [[47,31,9,9,W],[49,33,5,1,D],[49,36,5,1,D]] },
        burnout: { n: '전구 나감', sw: { '#FFE59A': '#5F5B82', '#F5C451': '#3A3660' } },
        tycoon: { n: '금괴 볼', over: [[7,34,9,4,G],[48,34,9,4,G],[8,39,7,3,LG],[49,39,7,3,LG]] },
        loanshark: { n: '볼 금고', sw: { '#C9E8FF': '#5F5B82' }, over: [[10,28,4,4,G],[50,28,4,4,G]] },
        hunter: { n: '꼬리 헤드램프', over: [[58,36,6,18,LG,0.4]] },
        vampire: { n: '피 주머니', sw: { '#C9E8FF': '#C0405A' } },
        influencer: { n: '셀카봉 꼬리', over: [[58,26,2,20,'#5F5B82'],[55,22,8,5,D],[56,23,6,3,'#8FB4FF']] },
        broke: { n: '홀쭉 볼', drop: ['#C9E8FF', '#F5C451'] },
        boss: { n: '금니', over: [[30,40,3,2,G],[34,39,3,3,G]] }
      },
      rabbit: {
        base: { n: '수신 대기' },
        model: { n: '정렬 회로', over: [[20,46,8,1,'#8FB4FF'],[28,46,1,4,'#8FB4FF']] },
        miser: { n: '수신 차단', sw: { '#6FE3B3': '#5F5B82' }, over: [[18,-3,5,5,G],[19,-2,3,3,LG]] },
        owl: { n: '야간 수신', sw: { '#6FE3B3': '#FFE59A' }, over: [[26,0,2,2,LG],[28,-2,2,2,LG],[54,0,2,2,LG]] },
        spender: { n: '귀걸이', over: [[24,22,2,5,P],[44,22,2,5,P],[23,26,4,2,LG]] },
        thug: { n: '두 귀 다 꺾임', sw: { '#8FB4FF': '#F38BA3' }, over: [[10,2,8,6,'T'],[8,6,4,2,'#6FE3B3']] },
        runaway: { n: '안테나만', over: [[26,46,2,10,'#5F5B82'],[25,44,4,2,'#6FE3B3']] },
        scholar: { n: '제3의 눈 개안', over: [[27,28,8,7,D],[29,29,4,5,'#6FE3B3'],[30,30,2,2,W]] },
        burnout: { n: '노이즈', sw: { '#8FB4FF': '#5F5B82', '#6FE3B3': '#5F5B82' }, over: [[14,0,4,1,W],[30,4,4,1,W],[44,0,4,1,W],[52,12,3,1,W]] },
        tycoon: { n: '금 회로', sw: { '#8FB4FF': '#F5C451' } },
        loanshark: { n: '청구서 수신', over: [[48,-2,9,7,W],[50,0,5,1,D],[50,2,4,1,D]] },
        hunter: { n: '레이더 귀', over: [[15,-2,11,2,'#6FE3B3'],[44,2,11,2,'#6FE3B3']] },
        vampire: { n: '박쥐 귀', sw: { '#6FE3B3': '#F38BA3' }, over: [[14,10,4,4,D],[46,12,4,4,D],[14,18,4,3,D]] },
        influencer: { n: '생방송 중', over: [[52,0,5,5,'#F05A3A'],[53,1,3,3,P]] },
        broke: { n: '끊긴 신호', drop: ['#8FB4FF'], over: [[20,12,2,2,D],[19,14,1,2,D]] },
        boss: { n: '감시의 눈', over: [[29,30,4,4,D],[30,31,2,2,'#F05A3A'],[27,29,8,1,'#F05A3A']] }
      }
    };

    function glasses(a, c) {
      var L = a.eyes[0].box, R = a.eyes[1].box, out = [];
      a.eyes.forEach(function (e) { var b = e.box; out = out.concat(outline(b[0]-2, b[1]-2, b[2]+4, b[3]+4, c)); });
      var bx = L[0] + L[2] + 2;
      out.push([bx, L[1] + Math.floor(L[3] / 2), Math.max(1, R[0] - 2 - bx), 1, c]);
      return out;
    }
    function shades(a) {
      var L = a.eyes[0].box, R = a.eyes[1].box, out = [];
      a.eyes.forEach(function (e) { var b = e.box; out.push([b[0]-2, b[1]-1, b[2]+4, b[3]+2, D]); out.push([b[0]-1, b[1], 2, 1, '#8FB4FF']); });
      var bx = L[0] + L[2] + 2;
      out.push([bx, L[1], Math.max(1, R[0] - 2 - bx), 1, D]);
      return out;
    }
    function item(a, rects) { var ix = a.item[0], iy = a.item[1]; return rects.map(function (r) { return [ix + r[0], iy + r[1], r[2], r[3], r[4]]; }); }

    var F = {
      base: function () { return {}; },
      model: function (a) { return { over: glasses(a, D) }; },
      miser: function (a) { return { tint: ['#F5C451', 0.25], over: item(a, [[0,3,10,9,'#9A6E12'],[2,0,6,3,'#9A6E12'],[4,5,2,5,G]]) }; },
      owl: function (a) { return { tint: ['#5B8FE8', 0.4], eyes: 'owl', over: [[a.cx-12, a.hatY-6, 4, 6, '#5B8FE8'], [a.cx+8, a.hatY-6, 4, 6, '#5B8FE8']] }; },
      spender: function (a) { return { over: [[a.cx-9, a.hatY-6, 7, 6, P], [a.cx+2, a.hatY-6, 7, 6, P], [a.cx-2, a.hatY-5, 4, 4, '#E8708E'], [2, 4, 2, 2, G], [58, 10, 2, 2, G], [4, 20, 1, 1, G]] }; },
      thug: function (a) {
        var o = [[a.cx-10, a.hatY-5, 20, 5, D], [a.cx-7, a.hatY-8, 14, 3, D], [a.cx-7, a.hatY-3, 14, 1, P]];
        a.eyes.forEach(function (e, i) { var b = e.box; o.push([b[0]-1, b[1]-3, b[2]+2, 2, D]); o.push(i === 0 ? [b[0]+b[2]-1, b[1]-1, 2, 1, D] : [b[0]-1, b[1]-1, 2, 1, D]); });
        var R = a.eyes[1].box; o.push([R[0]+R[2]+1, R[1]+R[3]+1, 5, 2, W]);
        return { tint: ['#7A3A4A', 0.3], eyes: 'flat', over: o, bad: true };
      },
      runaway: function (a) {
        return { replace: [[12, 54, 40, 4, '#2D2A4A'], [22, 30, 18, 14, W], [24, 33, 14, 1, '#5F5B82'], [24, 36, 12, 1, '#5F5B82'], [24, 39, 9, 1, '#5F5B82'], [10, 48, 4, 4, a.primary[0]], [13, 50, 2, 2, a.primary[0]], [44, 50, 3, 2, '#3A3660'], [50, 46, 3, 2, '#3A3660'], [56, 42, 3, 2, '#3A3660']], bad: true };
      },
      scholar: function (a) { return { over: glasses(a, D).concat([[a.cx-12, a.hatY-4, 24, 3, D], [a.cx-6, a.hatY-1, 12, 3, D], [a.cx+10, a.hatY-3, 1, 9, G], [a.cx+9, a.hatY+5, 3, 2, G]]).concat(item(a, [[0,0,10,12,'#5B8FE8'],[1,1,8,10,W],[5,0,1,12,'#5B8FE8']])) }; },
      burnout: function (a) {
        var o = [[a.cx-8, a.hatY-8, 4, 4, '#5F5B82'], [a.cx-1, a.hatY-12, 4, 4, '#5F5B82'], [a.cx+6, a.hatY-8, 4, 4, '#5F5B82']];
        a.eyes.forEach(function (e) { var b = e.box; o.push([b[0]-1, b[1]+b[3], b[2]+2, 2, '#5F4B7A']); });
        return { tint: ['#9A93A8', 0.5], eyes: 'half', over: o };
      },
      tycoon: function (a) {
        var R = a.eyes[1].box;
        return { tint: ['#F5C451', 0.6], over: [[a.cx-11, a.hatY-3, 22, 3, D], [a.cx-6, a.hatY-15, 12, 12, D], [a.cx-6, a.hatY-6, 12, 2, G]].concat(outline(R[0]-2, R[1]-2, R[2]+4, R[3]+4, '#9A6E12')).concat([[R[0]+R[2]+1, R[1]+R[3]+2, 1, 6, '#9A6E12']]) };
      },
      loanshark: function (a) {
        return { tint: ['#C9A23A', 0.5], eyes: 'slit', bad: true, over: [[a.cx-8, a.hatY-5, 16, 5, '#5B4A1A'], [a.cx-10, a.hatY-1, 20, 2, '#5B4A1A']].concat(item(a, [[0,0,10,12,W],[2,3,6,1,'#5F5B82'],[2,6,6,1,'#5F5B82'],[2,9,6,1,'#5F5B82']])) };
      },
      hunter: function (a) {
        var L = a.eyes[0].box, R = a.eyes[1].box, top = Math.min(L[1], R[1]) - 3, h = Math.max(L[3], R[3]) + 6;
        var o = [[L[0]-4, top, R[0]+R[2]+8-L[0], h, D]];
        a.eyes.forEach(function (e) { var b = e.box; o.push([b[0]-1, b[1]-1, b[2]+2, b[3]+2, '#6FE3B3']); o.push([b[0]+Math.floor(b[2]/2)-1, b[1]+Math.floor(b[3]/2)-1, 2, 2, D]); });
        return { tint: ['#3A5BA8', 0.45], eyes: 'none', over: o };
      },
      vampire: function (a) {
        return { tint: ['#E8E4F5', 0.65], eyes: 'red', bad: true,
          under: [[a.cx-22, a.hatY+6, 44, 40, '#3A2A3A'], [a.cx-24, a.hatY+2, 8, 8, '#5A2A3A'], [a.cx+16, a.hatY+2, 8, 8, '#5A2A3A']],
          over: [[a.cx-8, a.hatY-2, 16, 3, D], [a.cx-2, a.hatY+1, 4, 2, D], [a.cx-4, a.mouthY+2, 2, 3, W], [a.cx+2, a.mouthY+2, 2, 3, W]] };
      },
      influencer: function (a) {
        return { eyes: 'none', over: shades(a).concat([[a.cx-8, a.hatY-5, 16, 5, G], [a.cx-8, a.hatY-8, 3, 3, G], [a.cx-1, a.hatY-10, 3, 5, G], [a.cx+5, a.hatY-8, 3, 3, G], [a.cx-1, a.hatY-3, 2, 2, P], [a.cx-14, a.mouthY+6, 28, 3, '#6FE3B3'], [a.cx+6, a.mouthY+9, 4, 6, '#6FE3B3']]) };
      },
      broke: function (a) {
        return { tint: ['#E7A3B3', 0.2], eyes: 'swirl', bad: true, over: [[a.cx-14, a.hatY-6, 3, 3, G], [a.cx+12, a.hatY-10, 3, 3, G], [a.cx+4, a.hatY-14, 2, 2, G]].concat(item(a, [[0,0,10,9,'#9A6E12'],[2,-2,6,2,'#9A6E12'],[4,9,2,4,'#5F5B82']])) };
      },
      boss: function (a) {
        var R = a.eyes[1].box;
        return { tint: ['#7A3A4A', 0.45], eyes: 'none', bad: true, wrap: 'transform: scale(1.14); transform-origin: 50% 100%;',
          over: shades(a).concat([[a.cx-12, a.hatY-2, 24, 3, D], [a.cx-7, a.hatY-9, 14, 7, D], [a.cx-7, a.hatY-4, 14, 2, P], [R[0]+R[2]+3, R[1]-3, 1, R[3]+7, W], [R[0]+R[2]+2, R[1]+1, 3, 1, W], [a.cx-12, a.mouthY+6, 24, 2, G], [a.cx-2, a.mouthY+8, 4, 4, G]]) };
      }
    };

    var FORMS = [['base','아기',0],['model','모범생',1],['miser','구두쇠',1],['owl','올빼미',1],['spender','사치쟁이',1],['thug','불량배',1],['runaway','가출',1],['scholar','박사',2],['burnout','번아웃',2],['tycoon','재벌',2],['loanshark','고리대금',2],['hunter','사냥꾼',2],['vampire','흡혈귀',2],['influencer','인플루언서',2],['broke','탕진잼',2],['boss','조직 보스',2]];
    
function eyeRects(a, mode, tintFn) {
      var out = [];
      a.eyes.forEach(function (e) {
        var b = e.box;
        if (mode === 'none') return;
        if (mode === 'owl') {
          var s = Math.max(b[2], b[3]) + 3, x = b[0] + Math.floor(b[2] / 2) - Math.floor(s / 2), y = b[1] + Math.floor(b[3] / 2) - Math.floor(s / 2);
          out.push([x, y, s, s, G]); out.push([x + Math.floor(s / 2) - 1, y + Math.floor(s / 2) - 1, 2, 2, D]); return;
        }
        if (mode === 'slit') { out.push([b[0] - 1, b[1] + Math.floor(b[3] / 2), b[2] + 2, 2, a.ink]); return; }
        if (mode === 'swirl') { out = out.concat(outline(b[0] - 1, b[1] - 1, b[2] + 2, b[3] + 2, a.ink)); out.push([b[0] + Math.floor(b[2] / 2) - 1, b[1] + Math.floor(b[3] / 2) - 1, 2, 2, a.ink]); return; }
        e.draw.forEach(function (r) { out.push([r[0], r[1], r[2], r[3], mode === 'red' ? P : r[4]]); });
        if (mode === 'half') { out.push([b[0], b[1], b[2], Math.ceil(b[3] / 2), tintFn(a.primary[0])]); return; }
        if (mode === 'normal') e.shine.forEach(function (r) { out.push(r); });
      });
      return out;
    }

    
var BY_KEY = {};
S.forEach(function (a) { BY_KEY[a.key] = a; });

// Per-species part motion (the "모션" board). Body rect index -> CSS class (+ delay class).
// Overlays are extra rects that only exist for motion (twinkles, smoke, waves).
var MOTION = {
  squirrel: { parts: {}, overlay: [[48,22,3,3,W,null,'m-twinkle'],[52,30,3,3,W,null,'m-twinkle d2'],[44,38,3,3,W,null,'m-twinkle d4']],
              earn: [[57,2,5,8,LG,null,'e-grow']] },
  mole: { parts: {}, peek: [0, 1], overlay: [[28,10,8,4,W,null,'m-blink'],[10,50,2,2,G,null,'m-twinkle'],[50,52,2,2,G,null,'m-twinkle d3']],
          earn: [[26,8,12,8,LG,0.6,'e-flash']] },
  robot: { parts: {}, overlay: [[29,-4,6,6,'#A9A3C9',null,'m-smoke'],[30,-4,5,5,'#A9A3C9',null,'m-smoke d3'],[28,-4,4,4,'#A9A3C9',null,'m-smoke d4']],
           earn: [[24,44,16,6,'#FFE59A',null,'e-flash']] },
  penguin: { parts: { 2: 'm-twinkle', 3: 'm-twinkle d1', 4: 'm-twinkle d2', 5: 'm-twinkle d3' }, whole: 'm-waddle', overlay: [],
             earn: [[29,22,6,4,LG,null,'e-flash']] },
  hamster: { parts: { 2: 'm-flick', 3: 'm-flick d2', 4: 'm-flick d1', 5: 'm-flick d3', 10: 'e-puff', 11: 'e-puff', 20: 'm-blink', 21: 'm-blink' }, overlay: [], earn: [] },
  rabbit: { parts: { 9: 'm-eye3', 10: 'm-eye3', 13: 'm-flow', 14: 'm-flow d1', 15: 'm-flow d2', 16: 'm-flow d3' },
            overlay: [[18,-4,6,6,'none',null,'m-wave','#6FE3B3'],[47,1,6,6,'none',null,'m-wave d4','#F5C451']], earn: [] }
};

// Which forms already draw something on the head / over the eyes, so shop items skip that slot.
var OWN_HEAD = { thug: 1, spender: 1, scholar: 1, tycoon: 1, loanshark: 1, vampire: 1, influencer: 1, boss: 1, owl: 1, broke: 1, burnout: 1 };
var OWN_FACE = { model: 1, scholar: 1, hunter: 1, influencer: 1, boss: 1 };

function rect(r, cls) {
  var x = r[0], y = r[1], w = r[2], h = r[3], c = r[4], o = r[5];
  var a = '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '"';
  if (r[7]) a += ' fill="none" stroke="' + r[7] + '" stroke-width="1"';
  else a += ' fill="' + c + '"';
  if (o != null && o !== 1) a += ' opacity="' + o + '"';
  if (cls) a += ' class="' + cls + '"';
  return a + '/>';
}

export const SPECIES_KEYS = S.map(function (a) { return a.key; });
export function speciesInfo(key) { var a = BY_KEY[key]; return a ? { key: a.key, name: a.name, part: a.part } : null; }

// Shop items are drawn for mochi's head and eyes; move them onto this species.
export function itemOffset(key, slot) {
  var a = BY_KEY[key], m = BY_KEY.mochi;
  if (!a || key === 'mochi') return null;
  if (slot === 'head') return [a.cx - m.cx, a.hatY - m.hatY];
  if (slot === 'face') {
    var ey = a.eyes[0].box[1] + a.eyes[0].box[3] / 2, my = m.eyes[0].box[1] + m.eyes[0].box[3] / 2;
    return [a.cx - m.cx, Math.round(ey - my)];
  }
  return [0, 0];
}
export function peeks(key) { return !!(MOTION[key] || {}).peek; }
export function formOwnsSlot(form, slot) { return slot === 'head' ? !!OWN_HEAD[form] : slot === 'face' ? !!OWN_FACE[form] : false; }

// SVG markup for one species in one form. Eyes are grouped (<g class="eyes">) for blinking,
// motion parts carry classes, earn-only rects sit in <g class="earn">.
export function speciesMarkup(key, form) {
  var a = BY_KEY[key];
  if (!a) return null;
  var o = (F[form] || F.base)(a);
  var sg = (SIG[a.key] || {})[form] || {};
  var sw = sg.sw || {}, drop = sg.drop || [];
  var tint = function (c) { return (o.tint && a.primary.indexOf(c) >= 0) ? mix(c, o.tint[0], o.tint[1]) : c; };
  var paint = function (c) { return sw[c] ? sw[c] : tint(c); };
  var sigOver = (sg.over || []).map(function (r) { return [r[0], r[1], r[2], r[3], r[4] === 'T' ? tint(a.primary[0]) : r[4], r[5]]; });
  var mv = MOTION[a.key] || { parts: {}, overlay: [], earn: [] };
  if (o.replace) {
    var rep = (a.key === 'mochi' ? o.replace : o.replace.slice(0, 5)).concat(sigOver);
    return { markup: rep.map(function (r) { return rect(r); }).join(''), wrap: '', whole: '' };
  }
  var under = (o.under || []).map(function (r) { return rect(r); }).join('');
  var body = '', ground = '';
  a.body.forEach(function (r, i) {
    if (drop.indexOf(r[4]) >= 0) return;
    var s = rect([r[0], r[1], r[2], r[3], paint(r[4]), r[5]], mv.parts[i]);
    if (mv.peek && mv.peek.indexOf(i) >= 0) ground += s; else body += s;
  });
  var eyes = '<g class="eyes">' + eyeRects(a, o.eyes || 'normal', tint).map(function (r) { return rect(r); }).join('') + '</g>';
  var over = (o.over || []).concat(sigOver).map(function (r) { return rect(r); }).join('');
  var motion = (mv.overlay || []).map(function (r) { return rect(r, r[6]); }).join('');
  var earn = '<g class="earn">' + (mv.earn || []).map(function (r) { return rect(r, r[6]); }).join('') + '</g>';
  var inner = under + body + eyes + over + motion + earn;
  // the mole pops out of its hole: the body is clipped at ground level, the ground drawn on top
  if (mv.peek) inner = '<clipPath id="tp-peek-clip"><rect x="-8" y="-24" width="80" height="70"/></clipPath>'
    + '<g clip-path="url(#tp-peek-clip)"><g class="m-peek">' + inner + '</g></g>' + ground;
  return { markup: inner, wrap: o.wrap || '', whole: mv.whole || '' };
}

// Anchor points the widget uses for form-motion overlays (smoke, glint, sparks).
export function anchor(key) {
  var a = BY_KEY[key] || BY_KEY.mochi;
  return { cx: a.cx, hatY: a.hatY, mouthY: a.mouthY, item: a.item, eye: a.eyes[0].box, eye2: a.eyes[1].box };
}
