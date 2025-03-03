import requests
import logging
import xml.etree.ElementTree as ET
from typing import Dict, Optional, List
import urllib3

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API URL 상수
JUSO_API_URL = "https://www.juso.go.kr/addrlink/addrLinkApi.do"
SOIL_API_URL = "https://apis.data.go.kr/1390802/SoilEnviron/SoilExam/getSoilExamList"

def search_address(address: str, api_key: str) -> Optional[Dict]:
    """도로명주소(juso.go.kr) API를 사용하여 주소 검색하는 함수"""
    logger.info(f"주소 검색 시작: {address}")
    
    params = {
        'confmKey': api_key,
        'keyword': address,
        'currentPage': '1',
        'countPerPage': '10',
        'resultType': 'json',
        'hstryYn': 'Y',
        'firstSort': 'location',
        'addInfoYn': 'Y'
    }
    
    try:
        response = requests.get(JUSO_API_URL, params=params)
        response.raise_for_status()
        result = response.json()
        
        # 에러 체크
        error_code = result['results']['common']['errorCode']
        if error_code != "0":
            error_message = result['results']['common']['errorMessage']
            logger.error(f"주소 API 에러 발생: {error_code} - {error_message}")
            return {'error': error_message}  # 에러 메시지 반환
        
        # 검색 결과 체크
        if result['results']['common']['totalCount'] == "0":
            logger.warning("검색된 주소가 없습니다. 입력한 주소를 확인해주세요.")
            return {'error': "검색된 주소가 없습니다. 입력한 주소를 확인해주세요."}
        
        # 도로명/지번주소 확인
        address_info = result['results']['juso'][0]
        logger.info(f"도로명주소: {address_info['roadAddr']}")
        logger.info(f"지번주소: {address_info['jibunAddr']}")
        
        return address_info
        
    except requests.exceptions.RequestException as e:
        logger.error(f"주소 검색 중 오류 발생: {str(e)}")
        return {'error': f"주소 검색 중 오류가 발생했습니다: {str(e)}"}

def generate_pnu_code(address_info: Dict) -> str:
    """
    주소 정보로부터 PNU 코드 생성하는 함수
    
    PNU 코드 구성:
    (블로그 참조)
    - 광역시도코드(2자리)
    - 시군구코드(3자리)
    - 읍면동코드(3자리)
    - 리코드(2자리)
    - 토지구분(1자리): 1(토지) or 2(임야) -> 혹시 다른 코드도 있는지 확인 필요
    - 본번(4자리)
    - 부번(4자리)
    """
    logger.info("PNU 코드 생성 시작")
    
    # 법정동코드 (10자리)
    bjd_code = address_info['admCd']
    
    # 산여부 확인 (mtYn: 0=대지, 1=산)
    land_type = "2" if address_info['mtYn'] == "1" else "1"
    
    # 본번과 부번 처리
    main_num = str(address_info['lnbrMnnm']).zfill(4)  # 본번 (4자리로 맞춤)
    sub_num = str(address_info['lnbrSlno']).zfill(4)   # 부번 (4자리로 맞춤)
    
    pnu_code = f"{bjd_code}{land_type}{main_num}{sub_num}"
    
    logger.info(f"생성 PNU 코드: {pnu_code}")
    logger.debug(f"PNU 코드 구성:")
    logger.debug(f"- 법정동코드: {bjd_code}")
    logger.debug(f"- 토지구분: {land_type} ({'임야' if land_type == '2' else '토지'})")
    logger.debug(f"- 본번: {main_num}")
    logger.debug(f"- 부번: {sub_num}")
    
    return pnu_code

def parse_soil_data(xml_data: str) -> List[Dict]:
    """
    토양 정보 API는 XML로 리스폰스 리턴, 해당 데이터 파싱하는 함수
    """
    logger.info("토양 정보 XML 파싱 시작")
    
    def safe_float(element, default=0.0):
        """XML 요소에서 안전하게 float 값을 추출하는 함수 (None 처리)"""
        if element is None or element.text is None:
            return default
        try:
            return float(element.text)
        except (ValueError, TypeError):
            return default
    
    try:
        # XML 파싱
        root = ET.fromstring(xml_data)
        
        # 결과 리스트
        results = []
        
        # items 태그 아래의 item 태그들을 순회
        for item in root.findall('.//item'):
            try:
                soil_data = {
                    'BJD_Code': item.find('BJD_Code').text or '',
                    'year': item.find('Any_Year').text or '',
                    'test_date': item.find('Exam_Day').text or '',
                    'exam_type': item.find('Exam_Type').text or '',
                    'address': item.find('PNU_Nm').text or '',
                    'pH': safe_float(item.find('ACID')),
                    'P2O5': safe_float(item.find('VLDPHA')),
                    'SiO2': item.find('VLDSIA').text if item.find('VLDSIA') is not None else '',
                    'OM': safe_float(item.find('OM')),
                    'Mg': safe_float(item.find('POSIFERT_MG')),
                    'K': safe_float(item.find('POSIFERT_K')),
                    'Ca': safe_float(item.find('POSIFERT_CA')),
                    'EC': safe_float(item.find('SELC'))
                }
                results.append(soil_data)
                logger.debug(f"파싱 데이터: {soil_data}")
            except (AttributeError, ValueError) as e:
                logger.warning(f"항목 파싱 중 오류 발생: {str(e)}")
                continue
        
        logger.info(f"토양 정보 파싱 완료: {len(results)}건")
        return results
        
    except ET.ParseError as e:
        logger.error(f"XML 파싱 중 오류 발생: {str(e)}")
        logger.debug(f"XML 데이터: {xml_data}")
        return []

def find_closest_address(target_jibun: Dict, results: List[Dict]) -> Optional[Dict]:
    """
    가장 가까운 지번의 토양 정보 찾는 함수 (완전 매칭되는 주소가 없는 경우 가장 가까운 지번 찾기)
    """
    closest_result = None
    min_diff = float('inf')
    
    target_num = int(target_jibun['main'])
    target_sub = int(target_jibun['sub']) if target_jibun['sub'] != '0' else 0
    
    for result in results:
        address = result['address']
        # 주소에서 지번 추출
        parts = address.split()
        last_part = parts[-1]
        
        try:
            if '-' in last_part:
                main, sub = map(int, last_part.split('-'))
            else:
                main = int(last_part)
                sub = 0
                
            #FIXME: 지번 차이 계산 (지번 숫자 차이로 계산: 맞는지 확인 필요)
            diff = abs(target_num - main) * 100 + abs(target_sub - sub)
            
            if diff < min_diff:
                min_diff = diff
                closest_result = result
                
        except (ValueError, IndexError):
            continue
    
    if closest_result:
        logger.info(f"가장 가까운 주소: {closest_result['address']} (지번: {target_jibun['main']}-{target_jibun['sub']})")
    
    return closest_result

def get_soil_info(bjd_code: str, api_key: str, location_info: Dict = None) -> Optional[Dict]:
    """법정동 코드로 토양 정보 조회하는 함수"""
    logger.info(f"토양 정보 조회 시작: 법정동코드 {bjd_code}")
    
    page_no = 1
    page_size = 10
    matched_results = []
    all_results = []
    
    while True:
        try:
            url = f"http://apis.data.go.kr/1390802/SoilEnviron/SoilExam/getSoilExamList?serviceKey={api_key}&BJD_Code={bjd_code}&Page_Size={page_size}&Page_No={page_no}"
            
            response = requests.get(url, verify=False)
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            response.raise_for_status()
            
            root = ET.fromstring(response.text)
            total_count_elem = root.find('.//Total_Count')
            rcdcnt_elem = root.find('.//Rcdcnt')
            
            # XML 응답에 필수 태그가 없는 경우 처리
            if total_count_elem is None or rcdcnt_elem is None:
                logger.error("XML 응답에서 필수 태그를 찾을 수 없습니다")
                break
                
            total_count = int(total_count_elem.text)
            current_page_count = int(rcdcnt_elem.text)
            
            if current_page_count == 0:
                break
                
            page_results = parse_soil_data(response.text)
            all_results.extend(page_results)
            
            if location_info:
                for result in page_results:
                    if (result['address'] == location_info['road_address']['full'] or 
                        result['address'] == location_info['jibun']['full']):
                        matched_results = [result]
                        logger.info(f"정확한 주소 매칭: {result['address']}")
                        break
            
            if matched_results or page_no * page_size >= total_count:
                break
                
            page_no += 1
            
        except requests.exceptions.RequestException as e:
            logger.error(f"토양 정보 조회 중 오류 발생: {str(e)}")
            break
    
    # 정확한 매칭이 없는 경우 가장 가까운 지번 찾기
    if not matched_results and all_results:
        closest_result = find_closest_address(location_info['jibun'], all_results)
        if closest_result:
            matched_results = [closest_result]
            logger.info("정확한 매칭 결과는 없어 가장 가까운 지번의 결과를 반환합니다.")
    
    if not matched_results:
        logger.warning("토양 정보가 없습니다.")
        return None
        
    return {
        'soil_data': matched_results,
        'total_count': len(matched_results)
    }

def get_soil_info_by_address(address: str, juso_api_key: str, soil_api_key: str) -> Optional[Dict]:
    """주소로 토양 정보를 조회하는 함수"""
    try:
        # 주소 검색으로 법정동 코드 얻기
        address_info = search_address(address, juso_api_key)
        if not address_info:
            return None
            
        # 에러 체크
        if 'error' in address_info:
            return {'error': address_info['error']}  # 에러 메시지를 상위로 전달

        # 토양 정보 조회
        soil_info = get_soil_info(address_info['admCd'], soil_api_key, {
            'road_address': {'full': address_info['roadAddr']},
            'jibun': {
                'full': address_info['jibunAddr'],
                'main': address_info['lnbrMnnm'],
                'sub': address_info['lnbrSlno']
            }
        })
        if not soil_info or not soil_info.get('soil_data'):
            return None

        # 입력 주소와 결과 주소 비교하여 exact_match 결정
        input_address = address.replace(' ', '')
        result_address = soil_info['soil_data'][0]['address'].replace(' ', '')
        exact_match = input_address in result_address or result_address in input_address

        return {
            'soil_data': soil_info['soil_data'],
            'exact_match': exact_match,
            'matched_address': soil_info['soil_data'][0]['address']
        }

    except Exception as e:
        logger.error(f"토양 정보 조회 중 오류 발생: {str(e)}")
        return None

def main():
    JUSO_API_KEY = "devU01TX0FVVEgyMDI1MDMwMjEzNTYyNTExNTUxMDQ="
    SOIL_API_KEY = "AExC2xVOtaEE0vN/Yb3geQ2K2jifusUyQlPdt4sv1pI/v4nToQ/BU3WPQ2QgIFOXPy/fi8IPEz39XfnIQB932Q=="
    address = "전남 해남군 산이면 새상골길 292-17"
    
    result = get_soil_info_by_address(address, JUSO_API_KEY, SOIL_API_KEY)
    
    if result:
        for data in result['soil_data']:
            print(f"\n===토양 검사 세부내용===")
            print(f"검사일자: {data['test_date']}")
            print(f"검사유형: {data['exam_type']}")
            print(f"주소: {data['address']}")
            print(f"pH(산도): {data['pH']:.1f}")
            print(f"유기물(OM): {data['OM']:.1f} g/kg")
            print(f"유효인산(P2O5): {data['P2O5']:.1f} mg/kg")
            print(f"칼륨(K): {data['K']:.3f} cmol/kg")
            print(f"칼슘(Ca): {data['Ca']:.1f} cmol/kg")
            print(f"마그네슘(Mg): {data['Mg']:.3f} cmol/kg")
            print(f"전기전도도(EC): {data['EC']:.3f} dS/m")
            print(f"\n===토양 검사 세부내용 끝===")
    else:
        logger.error("토양 정보를 조회할 수 없습니다.")

if __name__ == "__main__":
    main() 