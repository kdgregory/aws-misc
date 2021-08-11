# Copyright 2018-2021 Keith D Gregory
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
################################################################################

""" This module encapsulates the log format of each ELB type as a separate
    class. Each provides a parse() method, which transforms the source data
    (passed as a BytesIO object) into a list of dicts containing log entries.

    If unable to parse the file, raises a ParseException that describes the
    problem.
    """

import gzip
import io
import re


class ParseException(Exception):
    
    def __init__(self, message, input_line=None):
        self.message = message
        self.input_line = input_line
        
        
class BaseParser:
    """ Common functionality for all parsers.
        """    
    
    def __init__(self):
        super().__init__()
        self._url_regex = re.compile((
            r'(?P<request_protocol>[^:]+)://'   
            r'(?P<request_host>[^:/]+)'
            r':?(?P<request_port>[\d]+)/'
            r'(?P<request_path>[^?]+)'
            r'[?]?(?P<request_query>.*)'
        ))
    
    
    def parse(self, buffer):
        """ Expects a buffer containing individual log lines, and parses those
            lines using the subclass regex.
            """
        buffer.seek(0)
        content = io.TextIOWrapper(buffer, encoding='utf-8')
        result = []
        for line in content.readlines():
            match = self._regex.match(line)
            if not match:
                raise ParseException("failed to match regex", line)
            entry = dict(match.groupdict())
            request_url = entry.get('request_url', "")
            url_match = self._url_regex.match(request_url)
            if url_match:
                entry.update(url_match.groupdict())
            result.append(entry)
        return result


class ALBParser(BaseParser):
    """ Extracts records from an Application load balancer.
        """
    
    def __init__(self):
        super().__init__()
        self._regex = re.compile((
            r'(?P<request_type>[^ ]+) '                              
            r'(?P<timestamp>\d{4}-\d{2}-\d{2}T\d+:\d+:\d+\.\d+Z) '  
            r'(?P<elb_name>[^ ]+) '                                
            r'(?P<client_ip>[^:]+):'                                
            r'(?P<client_port>[^ ]+) '                                
            r'(?P<backend_address>[^ ]+) '                                
            r'(?P<request_processing_time>[0-9.-]+) '                             
            r'(?P<backend_processing_time>[0-9.-]+) '                             
            r'(?P<response_processing_time>[0-9.-]+) '                             
            r'(?P<elb_status_code>[^ ]+) '                                
            r'(?P<backend_status_code>[^ ]+) '                                
            r'(?P<received_bytes>\d+) '                                  
            r'(?P<sent_bytes>\d+) '                                  
            r'"(?P<request_method>[A-Z]+) '                              
            r'(?P<request_url>[^ ]+) '                                
            r'(?P<http_version>[^ ]+)" '                               
            r'"(?P<user_agent>.+?)" '                                
            r'(?P<ssl_cipher>[^ ]+) '                                
            r'(?P<ssl_protocol>[^ ]+) '                                
            r'(?P<target_group_arn>[^ ]+) '                                
            r'"(?P<trace_id>[^ ]+?)" '                             
            r'"(?P<sni_domain_name>[^ ]+)" '                              
            r'"(?P<chosen_cert_arn>[^ ]+)" '                              
            r'(?P<matched_rule_priority>[^ ]+) '                                
            r'(?P<request_creation_time>\d{4}-\d{2}-\d{2}T\d+:\d+:\d+\.\d+Z) '  
            r'"(?P<actions_executed>[^ ]+)" '                              
            r'"(?P<redirect_url>[^ ]+)" '                              
            r'"(?P<error_reason>[^ ]+)" '                              
            r'"(?P<target_port_list>[^ ]+)" '                        
            r'"(?P<target_status_list>[^ ]+)" '                             
            r'"(?P<classification>[^ ]+)" '                              
            r'"(?P<classification_reason>[^ ]+)"'                               
        ))

    def parse(self, buffer):
        try:
            unzipped = gzip.decompress(buffer.getvalue())
            buffer = io.BytesIO(unzipped)
        except Exception as ex:
            raise ParseException("failed to parse file") from ex
        return super().parse(buffer)


class CLBParser(BaseParser):
    """ Extracts records from a Classic load balancer.
        """

    def __init__(self):
        super().__init__()
        self._regex = re.compile(
            (
            r'(?P<timestamp>\d{4}-\d{2}-\d{2}T\d+:\d+:\d+\.\d+Z) '
            r'(?P<elb_name>[^ ]+) '                         
            r'(?P<client_ip>[^:]+):'                                
            r'(?P<client_port>[^ ]+) '                            
            r'(?P<backend_address>[^ ]+) '  
            r'(?P<request_processing_time>[0-9.-]+) ' 
            r'(?P<backend_processing_time>[0-9.-]+) ' 
            r'(?P<response_processing_time>[0-9.-]+) '
            r'(?P<elb_status_code>\d{3}) '   
            r'(?P<backend_status_code>\d{3}) '  
            r'(?P<received_bytes>\d+) ' 
            r'(?P<sent_bytes>\d+) '  
            r'"(?P<request_method>[A-Z]+) '
            r'(?P<request_url>[^ ]+) '    
            r'(?P<http_version>[^ ]+)" '                                     
            r'"(?P<user_agent>.+?)" '                         
            r'(?P<ssl_cipher>[^ ]+) '                                
            r'(?P<ssl_protocol>[^ ]+)'        
            ))

