import unittest
from combo_v20 import build_combos

class ComboV20Tests(unittest.TestCase):
    def pick(self, gid, p, market='matches'):
        return {'game_id': gid, 'probability': p, 'market': market, 'selection': f'{gid}:{p}', 'time': gid}

    def test_maximum_probability_not_target(self):
        picks = [self.pick(i, .62) for i in range(4)] + [self.pick(i, .70) for i in range(4)]
        prob, combo = build_combos(picks, 4, profile='Équilibré')[0]
        self.assertAlmostEqual(prob, .70**4)

    def test_distinct_games(self):
        picks = [self.pick(1,.70), self.pick(1,.65), self.pick(2,.69)]
        _, combo = build_combos(picks, 2, profile='Équilibré')[0]
        self.assertEqual(len({x['game_id'] for x in combo}), 2)

    def test_invalid_probs(self):
        picks = [self.pick(1,float('nan')), self.pick(2,.65), self.pick(3,.67)]
        self.assertEqual(len(build_combos(picks,2,profile='Équilibré')),1)

    def test_insufficient_games(self):
        self.assertEqual(build_combos([self.pick(1,.7)],2),[])

    def test_top_n_order(self):
        picks = [self.pick(i,p) for i,p in enumerate([.7,.69,.68,.67,.66])]
        result = build_combos(picks,3,top_n=4,profile='Équilibré')
        self.assertEqual(len(result),4)
        self.assertEqual([p for p,_ in result],sorted([p for p,_ in result],reverse=True))

if __name__ == '__main__':
    unittest.main()
