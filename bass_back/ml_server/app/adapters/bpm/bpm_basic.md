sampling_rate -> 1초를 몇개로 나누는가
    22050 Hz 가 국룰(고주파 버리고 가기위함)

frame_length -> 한번에 보는 구간 크기 = 한번의 몇개를 분석할까
hop_length -> 한번에 넘어갈 구간 크기 = 한번에 몇개를 건너뛸까

512/22050=0.023
hop_length/sampling_rate = 0.023초씩 건너뜀

2048/22050= 0.093
frame_length/sampling_rate = 0.093초씩 분석함