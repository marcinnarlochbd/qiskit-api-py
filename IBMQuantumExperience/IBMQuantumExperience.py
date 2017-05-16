import requests
import time
import datetime
import json

config_base = {
    'url': 'https://quantumexperience.ng.bluemix.net/api'
}


class _Credentials:
    def __init__(self, token, config=None):
        self.token_unique = token
        if config and config.get('url', None):
            self.config = config
        else:
            self.config = config_base

        self.data_credentials = {}
        self.obtain_token()

    def obtain_token(self):
        self.data_credentials = requests.post(self.config.get('url') + "/users/loginWithToken",
                                              data={'apiToken': self.token_unique}).json()

        if not self.get_token():
            print('ERROR: Not token valid')

    def get_token(self):
        return self.data_credentials.get('id', None)

    def get_user_id(self):
        return self.data_credentials.get('userId', None)

    def get_config(self):
        return self.config


class _Request:
    def __init__(self, token, config=None):
        self.credential = _Credentials(token, config)

    def check_token(self, respond):
        if respond.status_code == 401:
            self.credential.obtain_token()
            return False
        return True

    def post(self, path, params='', data=None):
        if data is None:
            data = {}
        headers = {'Content-Type': 'application/json'}
        respond = requests.post(
            self.credential.config['url'] + path + '?access_token=' + str(self.credential.get_token()) + params,
            data=data,
            headers=headers)
        if not self.check_token(respond):
            respond = requests.post(
                self.credential.config['url'] + path + '?access_token=' + str(self.credential.get_token()) + params,
                data=data, headers=headers)
        return respond.json()

    def get(self, path, params='', withToken=True):
        if (withToken):
            access_token = self.credential.get_token()
            if access_token:
                access_token = '?access_token=' + str(access_token)
            else:
                access_token = ''
        else:
            access_token = ''

        respond = requests.get(
            self.credential.config['url'] + path + access_token + params)
        if not self.check_token(respond):
            respond = requests.get(
                self.credential.config['url'] + path + access_token + params)
        return respond.json()


class IBMQuantumExperience:

    __names_device_5qxv2 = ['ibmqx5qv2', 'ibmqx2', 'qx5qv2', 'qx5q', 'real']
    __names_device_5qxv3 = ['ibmqx3']
    __names_device_simulator = ['simulator']

    def __init__(self, token, config=None):
        self.req = _Request(token, config)

    def _check_device(self, device, endpoint):
        device = device.lower()
        if endpoint == 'experiment':
            if device in self.__names_device_5qxv2:
                return 'real'
            elif device in self.__names_device_5qxv3:
                return 'ibmqx3'
            elif device in self.__names_device_simulator:
                return 'sim_trivial_2'
        elif endpoint == 'job':
            if device in self.__names_device_5qxv2:
                return 'real'
            elif device in self.__names_device_5qxv3:
                return 'ibmqx3'
            elif device in self.__names_device_simulator:
                return 'simulator'
        elif endpoint == 'status':
            if device in self.__names_device_5qxv2:
                return 'chip_real'
            elif device in self.__names_device_5qxv3:
                return 'ibmqx3'
        return None

    def _check_credentials(self):
        if not self.req.credential.get_token():
            return False
        return True

    def get_execution(self, id_execution):
        if not self._check_credentials():
            respond = {}
            respond["error"] = "Not credentials valid"
            return respond
        execution = self.req.get('/Executions/' + id_execution, '')
        if execution["codeId"]:
            execution['code'] = self.get_code(execution["codeId"])
        return execution

    def get_result_from_execution(self, id_execution):
        if not self._check_credentials():
            respond = {}
            respond["error"] = "Not credentials valid"
            return respond
        execution = self.req.get('/Executions/' + id_execution, '')
        result = {}
        if 'result' in execution:
            if execution["result"]["data"].get('p', None):
                result["measure"] = execution["result"]["data"]["p"]
            if execution["result"]["data"].get('valsxyz', None):
                result["bloch"] = execution["result"]["data"]["valsxyz"]

        return result

    def get_code(self, id_code):
        if not self._check_credentials():
            respond = {}
            respond["error"] = "Not credentials valid"
            return respond
        code = self.req.get('/Codes/' + id_code, '')
        executions = self.req.get('/Codes/' + id_code + '/executions', 'filter={"limit":3}')
        if isinstance(executions, list):
            code["executions"] = executions
        return code

    def get_image_code(self, id_code):
        if not self._check_credentials():
            respond = {}
            respond["error"] = "Not credentials valid"
            return respond
        return self.req.get('/Codes/' + id_code + '/export/png/url', '')

    def get_last_codes(self):
        if not self._check_credentials():
            respond = {}
            respond["error"] = "Not credentials valid"
            return respond
        return self.req.get('/users/' +
                            str(self.req.credential.get_user_id()) +
                            '/codes/lastest', '&includeExecutions=true')['codes']

    def run_experiment(self, qasm, device='simulator', shots=1, name=None, timeout=60):
        if not self._check_credentials():
            respond = {}
            respond["error"] = "Not credentials valid"
            return respond
        data = {}
        qasm = qasm.replace('IBMQASM 2.0;', '')
        qasm = qasm.replace('OPENQASM 2.0;', '')
        data['qasm'] = qasm
        data['codeType'] = 'QASM2'
        if name is None:
            name = 'Experiment #' + datetime.date.today().strftime("%Y%m%d%H%M%S")
        data['name'] = name

        device_type = self._check_device(device, 'experiment')

        if not device_type:
            respond = {}
            respond["error"] = "Device " + device + " not exits in Quantum Experience. Only allow ibmqx2 or simulator"
            return respond

        execution = self.req.post('/codes/execute', '&shots=' + str(shots) + '&deviceRunType=' + device_type,
                                  json.dumps(data))
        respond = {}
        # noinspection PyBroadException
        try:
            status = execution["status"]["id"]
            id_execution = execution["id"]
            result = {}
            respond["status"] = status
            respond["idExecution"] = id_execution
            respond["idCode"] = execution["codeId"]
            if status == "DONE":
                if execution["result"]:
                    if execution["result"]["data"].get('p', None):
                        result["measure"] = execution["result"]["data"]["p"]
                    if execution["result"]["data"].get('valsxyz', None):
                        result["bloch"] = execution["result"]["data"]["valsxyz"]
                    respond["result"] = result
                    return respond
            elif status == "ERROR":
                return respond
            else:
                if timeout:
                    for i in range(1, timeout):
                        print("Waiting for results...")
                        result = self.get_result_from_execution(id_execution)
                        if len(result) > 0:
                            respond["status"] = 'DONE'
                            respond["result"] = result
                            return respond
                        else:
                            time.sleep(2)
                    return respond
                else:
                    return respond
        except Exception:
            respond["error"] = execution
            return respond

    def run_job(self, qasms, device='simulator', shots=1, max_credits=3):
        if not self._check_credentials():
            respond = {}
            respond["error"] = "Not credentials valid"
            return respond
        data = {}
        for qasm in qasms:
            qasm['qasm'] = qasm['qasm'].replace('IBMQASM 2.0;', '')
            qasm['qasm'] = qasm['qasm'].replace('OPENQASM 2.0;', '')
        data['qasms'] = qasms
        data['shots'] = shots
        data['maxCredits'] = max_credits
        data['backend'] = {}

        device_type = self._check_device(device, 'job')

        if not device_type:
            respond = {}
            respond["error"] = "Device " + device + " not exits in Quantum Experience. Only allow ibmqx2 or simulator"
            return respond

        data['backend']['name'] = device_type

        job = self.req.post('/Jobs', data=json.dumps(data))
        return job

    def get_job(self, id_job):
        if not self._check_credentials() or not id_job:
            respond = {}
            respond["error"] = "Not credentials valid"
            return respond
        job = self.req.get('/Jobs/' + id_job)
        return job

    def device_status(self, device='ibmqx2'):
        device_type = self._check_device(device, 'status')
        if not device_type:
            respond = {}
            respond["error"] = "Device " + device + " not exits in Quantum Experience Real Devices. Only allow ibmqx2"
            return respond
        status = self.req.get('/Status/queue?device=' + device_type, withToken=False)["state"]
        ret = {}
        ret['available'] = False
        if status:
            ret['available'] = True
        return ret
