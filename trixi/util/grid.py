import json


class GridSearch(dict):

    def all_combinations(self):

        combinations = []
        zero_key = sorted(self.keys())[0]
        inner_dict = self.copy()
        del inner_dict[zero_key]

        for val in self[zero_key]:

            if len(inner_dict) == 0:
                combinations.append({zero_key: val})
            else:
                for combination in GridSearch(inner_dict):
                    combination[zero_key] = val
                    combinations.append(combination)

        return combinations

    def __iter__(self):

        self._counter = 0
        self._all_combinations = self.all_combinations()
        self._max = len(self._all_combinations)
        return self

    def __next__(self):

        if self._counter >= self._max:
            raise StopIteration

        self._counter += 1
        return self._all_combinations[self._counter - 1]

    def read(self, fp):

        if not hasattr(fp, "read"):
            fp = open(fp, "r")
        self.update(json.load(fp))

        return self
