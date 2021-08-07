""" This module encapsulates the log format of each ELB type as a separate
    class. Each provides a parse() method, which transforms the source data
    (passed as a BytesIO object) into a list of dicts containing log entries.

    If unable to parse the file, raises a ParseException that describes the
    problem.
    """

import gzip
import io
import logging
import re


LOGGER = logging.getLogger(__name__)


class ParseException(Exception):
    
    def __init__(self, message, input_line=None):
        self.message = message
        self.input_line = input_line


class ALBParser:
    """ Extracts records from an Application load balancer.
        """
    
    def __init__(self):
        self._regex = re.compile((
            r'^(?P<request_type>[^ ]+) '                              
            r'(?P<timestamp>\d{4}-\d{2}-\d{2}T\d+:\d+:\d+\.\d+Z) '  
            r'(?P<elb_resource_id>[^ ]+) '                                
            r'(?P<client_address>[^ ]+) '                                
            r'(?P<backend_address>[^ ]+) '                                
            r'(?P<request_processing_time>[0-9.-]+) '                             
            r'(?P<backend_processing_time>[0-9.-]+) '                             
            r'(?P<response_processing_time>[0-9.-]+) '                             
            r'(?P<elb_status_code>[^ ]+) '                                
            r'(?P<backend_status_code>[^ ]+) '                                
            r'(?P<received_bytes>\d+) '                                  
            r'(?P<sent_bytes>\d+) '                                  
            r'"(?P<http_method>[A-Z]+) '                              
            r'(?P<http_url>[^ ]+) '                                
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
        content = io.TextIOWrapper(buffer)
        result = []
        for line in content.readlines():
            match = self._regex.match(line)
            if match:
                result.append(dict(match.groupdict()))
            else:
                raise ParseException("failed to match regex", line)
        return result


class CLBParser:
    """ Extracts records from a Classic load balancer.
        """

    def __init__(self):
        # TODO - change this to use named fields
        self._regex = re.compile(
            (
            r'^(\d{4}-\d{2}-\d{2}T\d+:\d+:\d+\.\d+Z) '    # timestamp
            r'([^ ]+) '                                   # elb_name
            r'(\d+\.\d+\.\d+\.\d+):(\d+) '                # client_ip, client_port
            r'(\d+\.\d+\.\d+\.\d+):(\d+) '                # backend_ip, backend_port
            r'([0-9.-]+) '                                # request_processing_time
            r'([0-9.-]+) '                                # backend_processing_time
            r'([0-9.-]+) '                                # response_processing_time
            r'(\d{3}) '                                   # elb_status_code
            r'(\d{3}) '                                   # backend_status_code
            r'(\d+) '                                     # received_bytes
            r'(\d+) '                                     # sent_bytes
            r'"([A-Z]+) '                                 # http_method
            r'([^ ]+) '                                   # http_url
            r'([^ ]+)" '                                  # http_version
            r'"(.+)" '                                    # user_agent
            r'(.+) '                                      # ssl_cipher
            r'(.+)$'                                      # ssl_protocol
            ))

    def parse(self, buffer):
        pass
